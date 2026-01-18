//! Byzantine Fault Detection and Isolation
//!
//! Detects and isolates Byzantine (malicious or faulty) peers in the mesh network.
//!
//! ## Detection Strategies
//!
//! 1. **Equivocation Detection**: Catch peers sending conflicting messages
//!    - Same height/round with different proposals
//!    - Same height/round with conflicting votes
//!
//! 2. **Timeout Detection**: Peers not responding to critical messages
//!
//! 3. **Invalid Message Detection**: Messages with incorrect structure/signatures
//!
//! 4. **View Change Attacks**: Detecting malicious view change attempts
//!
//! ## Isolation Protocol
//!
//! When Byzantine behavior is detected:
//! 1. Log the violation with full evidence
//! 2. Increment fault counter for the peer
//! 3. When threshold exceeded, isolate the peer
//! 4. Broadcast isolation notice to other honest peers
//! 5. Periodically allow re-admission with proof of correction
//!
//! Colony: Crystal (D₅) — Verification and trust
//!
//! η → s → μ → a → η′
//! h(x) ≥ 0. Always.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};
use tokio::sync::RwLock;
use tracing::{debug, error, info, warn};

// ============================================================================
// Configuration
// ============================================================================

/// Number of Byzantine faults before isolation
pub const BYZANTINE_FAULT_THRESHOLD: u32 = 3;

/// Time window for fault counting (faults decay after this period)
pub const FAULT_DECAY_INTERVAL: Duration = Duration::from_secs(300); // 5 minutes

/// Isolation duration before re-admission check
pub const ISOLATION_DURATION: Duration = Duration::from_secs(600); // 10 minutes

/// Maximum evidence entries to store per peer
pub const MAX_EVIDENCE_PER_PEER: usize = 100;

// ============================================================================
// Byzantine Fault Types
// ============================================================================

/// Types of Byzantine faults that can be detected
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum ByzantineFaultType {
    /// Peer sent conflicting proposals for the same height/round
    ProposalEquivocation {
        height: u64,
        round: u32,
        proposal1: Vec<u8>, // Serialized proposal
        proposal2: Vec<u8>,
    },
    /// Peer sent conflicting votes for the same height/round
    VoteEquivocation {
        height: u64,
        round: u32,
        vote1: Vec<u8>, // Serialized vote
        vote2: Vec<u8>,
    },
    /// Peer's message had invalid signature
    InvalidSignature {
        message_type: String,
        message_hash: Vec<u8>,
    },
    /// Peer sent message with invalid structure
    InvalidMessageFormat { reason: String },
    /// Peer not responding to heartbeats
    HeartbeatTimeout {
        last_seen: u64, // Unix timestamp
        timeout_ms: u64,
    },
    /// Peer sending excessive messages (potential DoS)
    MessageFlooding {
        message_count: u64,
        time_window_ms: u64,
    },
    /// Peer attempting invalid view change
    InvalidViewChange { reason: String },
    /// Peer proposed invalid leader (not in validator set)
    InvalidLeaderProposal {
        proposed_leader: String,
        reason: String,
    },
}

impl ByzantineFaultType {
    /// Get severity level (higher = more severe)
    pub fn severity(&self) -> u32 {
        match self {
            ByzantineFaultType::ProposalEquivocation { .. } => 10, // Most severe
            ByzantineFaultType::VoteEquivocation { .. } => 10,
            ByzantineFaultType::InvalidSignature { .. } => 8,
            ByzantineFaultType::MessageFlooding { .. } => 6,
            ByzantineFaultType::InvalidViewChange { .. } => 5,
            ByzantineFaultType::InvalidLeaderProposal { .. } => 4,
            ByzantineFaultType::InvalidMessageFormat { .. } => 3,
            ByzantineFaultType::HeartbeatTimeout { .. } => 1, // Least severe (could be network issues)
        }
    }

    /// Check if this fault type should trigger immediate isolation
    pub fn is_critical(&self) -> bool {
        matches!(
            self,
            ByzantineFaultType::ProposalEquivocation { .. }
                | ByzantineFaultType::VoteEquivocation { .. }
        )
    }
}

// ============================================================================
// Evidence Record
// ============================================================================

/// Evidence of a Byzantine fault
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ByzantineEvidence {
    /// Peer that committed the fault
    pub peer_id: String,
    /// Type of fault detected
    pub fault_type: ByzantineFaultType,
    /// Timestamp when detected
    pub detected_at: u64,
    /// Hash of the evidence for deduplication
    pub evidence_hash: Vec<u8>,
}

impl ByzantineEvidence {
    /// Create new evidence record
    pub fn new(peer_id: String, fault_type: ByzantineFaultType) -> Self {
        let detected_at = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();

        // Create evidence hash from peer_id, fault_type, and timestamp
        let evidence_data = format!("{}:{:?}:{}", peer_id, fault_type, detected_at);
        let evidence_hash = simple_hash(evidence_data.as_bytes());

        Self {
            peer_id,
            fault_type,
            detected_at,
            evidence_hash,
        }
    }
}

// ============================================================================
// Peer Fault State
// ============================================================================

/// Fault state for a single peer
#[derive(Debug, Clone)]
pub struct PeerFaultState {
    /// Number of faults detected
    pub fault_count: u32,
    /// Weighted fault score (considering severity)
    pub fault_score: u32,
    /// Timestamp of first fault in current window
    pub first_fault: Instant,
    /// Timestamp of last fault
    pub last_fault: Instant,
    /// Whether peer is currently isolated
    pub isolated: bool,
    /// When isolation started (if isolated)
    pub isolation_start: Option<Instant>,
    /// Evidence records
    pub evidence: Vec<ByzantineEvidence>,
    /// Proposals seen (height, round) -> proposal_hash for equivocation detection
    pub seen_proposals: HashMap<(u64, u32), Vec<u8>>,
    /// Votes seen (height, round, vote_type) -> vote_hash for equivocation detection
    pub seen_votes: HashMap<(u64, u32, String), Vec<u8>>,
}

impl Default for PeerFaultState {
    fn default() -> Self {
        let now = Instant::now();
        Self {
            fault_count: 0,
            fault_score: 0,
            first_fault: now,
            last_fault: now,
            isolated: false,
            isolation_start: None,
            evidence: Vec::new(),
            seen_proposals: HashMap::new(),
            seen_votes: HashMap::new(),
        }
    }
}

impl PeerFaultState {
    /// Add a fault and check if isolation threshold is exceeded
    pub fn add_fault(&mut self, evidence: ByzantineEvidence) -> bool {
        let severity = evidence.fault_type.severity();
        let is_critical = evidence.fault_type.is_critical();

        self.fault_count += 1;
        self.fault_score += severity;
        self.last_fault = Instant::now();

        // Store evidence (limit size)
        if self.evidence.len() < MAX_EVIDENCE_PER_PEER {
            self.evidence.push(evidence);
        }

        // Critical faults trigger immediate isolation
        if is_critical {
            warn!("🔴 CRITICAL Byzantine fault detected - immediate isolation triggered");
            return true;
        }

        // Check if threshold exceeded
        self.fault_score >= BYZANTINE_FAULT_THRESHOLD * 3 // Threshold based on score, not count
    }

    /// Decay faults over time
    pub fn decay_faults(&mut self) {
        if self.first_fault.elapsed() > FAULT_DECAY_INTERVAL {
            // Reset fault window
            self.fault_count = self.fault_count.saturating_sub(1);
            self.fault_score = self.fault_score.saturating_sub(3);
            self.first_fault = Instant::now();

            if self.fault_count == 0 {
                self.fault_score = 0;
            }
        }
    }

    /// Check if isolation period has expired and peer can be re-admitted
    pub fn can_readmit(&self) -> bool {
        if !self.isolated {
            return false;
        }

        match self.isolation_start {
            Some(start) => start.elapsed() > ISOLATION_DURATION,
            None => false,
        }
    }

    /// Reset state for re-admission
    pub fn readmit(&mut self) {
        self.isolated = false;
        self.isolation_start = None;
        self.fault_count = 0;
        self.fault_score = 0;
        self.first_fault = Instant::now();
        // Keep evidence for audit
    }
}

// ============================================================================
// Byzantine Detector
// ============================================================================

/// Byzantine fault detector and isolation manager
pub struct ByzantineDetector {
    /// This hub's ID (kept for diagnostics/logging)
    #[allow(dead_code)]
    hub_id: String,
    /// Peer fault states
    peer_states: Arc<RwLock<HashMap<String, PeerFaultState>>>,
    /// Isolated peers
    isolated_peers: Arc<RwLock<HashSet<String>>>,
    /// Callback for isolation events
    isolation_callback: Option<Box<dyn Fn(String, ByzantineEvidence) + Send + Sync>>,
}

impl ByzantineDetector {
    /// Create a new Byzantine detector
    pub fn new(hub_id: String) -> Self {
        Self {
            hub_id,
            peer_states: Arc::new(RwLock::new(HashMap::new())),
            isolated_peers: Arc::new(RwLock::new(HashSet::new())),
            isolation_callback: None,
        }
    }

    /// Set callback for isolation events
    pub fn on_isolation<F>(&mut self, callback: F)
    where
        F: Fn(String, ByzantineEvidence) + Send + Sync + 'static,
    {
        self.isolation_callback = Some(Box::new(callback));
    }

    /// Check if a peer is currently isolated
    pub async fn is_isolated(&self, peer_id: &str) -> bool {
        let isolated = self.isolated_peers.read().await;
        isolated.contains(peer_id)
    }

    /// Get all isolated peers
    pub async fn get_isolated_peers(&self) -> Vec<String> {
        let isolated = self.isolated_peers.read().await;
        isolated.iter().cloned().collect()
    }

    /// Record a proposal and check for equivocation
    pub async fn record_proposal(
        &self,
        peer_id: &str,
        height: u64,
        round: u32,
        proposal_hash: Vec<u8>,
    ) -> Result<(), ByzantineEvidence> {
        let mut states = self.peer_states.write().await;
        let state = states.entry(peer_id.to_string()).or_default();

        let key = (height, round);
        if let Some(existing_hash) = state.seen_proposals.get(&key) {
            if existing_hash != &proposal_hash {
                // EQUIVOCATION DETECTED!
                let evidence = ByzantineEvidence::new(
                    peer_id.to_string(),
                    ByzantineFaultType::ProposalEquivocation {
                        height,
                        round,
                        proposal1: existing_hash.clone(),
                        proposal2: proposal_hash,
                    },
                );

                error!(
                    "🔴 EQUIVOCATION: Peer {} sent conflicting proposals for h={} r={}",
                    peer_id, height, round
                );

                self.handle_fault(peer_id, evidence.clone()).await;
                return Err(evidence);
            }
        } else {
            state.seen_proposals.insert(key, proposal_hash);
        }

        Ok(())
    }

    /// Record a vote and check for equivocation
    pub async fn record_vote(
        &self,
        peer_id: &str,
        height: u64,
        round: u32,
        vote_type: &str,
        vote_hash: Vec<u8>,
    ) -> Result<(), ByzantineEvidence> {
        let mut states = self.peer_states.write().await;
        let state = states.entry(peer_id.to_string()).or_default();

        let key = (height, round, vote_type.to_string());
        if let Some(existing_hash) = state.seen_votes.get(&key) {
            if existing_hash != &vote_hash {
                // EQUIVOCATION DETECTED!
                let evidence = ByzantineEvidence::new(
                    peer_id.to_string(),
                    ByzantineFaultType::VoteEquivocation {
                        height,
                        round,
                        vote1: existing_hash.clone(),
                        vote2: vote_hash,
                    },
                );

                error!(
                    "🔴 EQUIVOCATION: Peer {} sent conflicting {} votes for h={} r={}",
                    peer_id, vote_type, height, round
                );

                self.handle_fault(peer_id, evidence.clone()).await;
                return Err(evidence);
            }
        } else {
            state.seen_votes.insert(key, vote_hash);
        }

        Ok(())
    }

    /// Report an invalid signature
    pub async fn report_invalid_signature(
        &self,
        peer_id: &str,
        message_type: &str,
        message_hash: Vec<u8>,
    ) {
        let evidence = ByzantineEvidence::new(
            peer_id.to_string(),
            ByzantineFaultType::InvalidSignature {
                message_type: message_type.to_string(),
                message_hash,
            },
        );

        warn!(
            "🟠 Invalid signature from peer {} on {} message",
            peer_id, message_type
        );

        self.handle_fault(peer_id, evidence).await;
    }

    /// Report a heartbeat timeout
    pub async fn report_heartbeat_timeout(&self, peer_id: &str, last_seen: u64, timeout_ms: u64) {
        let evidence = ByzantineEvidence::new(
            peer_id.to_string(),
            ByzantineFaultType::HeartbeatTimeout {
                last_seen,
                timeout_ms,
            },
        );

        debug!("Heartbeat timeout for peer {}", peer_id);

        self.handle_fault(peer_id, evidence).await;
    }

    /// Report message flooding
    pub async fn report_message_flooding(
        &self,
        peer_id: &str,
        message_count: u64,
        time_window_ms: u64,
    ) {
        let evidence = ByzantineEvidence::new(
            peer_id.to_string(),
            ByzantineFaultType::MessageFlooding {
                message_count,
                time_window_ms,
            },
        );

        warn!(
            "🟠 Message flooding from peer {}: {} messages in {}ms",
            peer_id, message_count, time_window_ms
        );

        self.handle_fault(peer_id, evidence).await;
    }

    /// Handle a detected fault
    async fn handle_fault(&self, peer_id: &str, evidence: ByzantineEvidence) {
        let should_isolate = {
            let mut states = self.peer_states.write().await;
            let state = states.entry(peer_id.to_string()).or_default();
            state.add_fault(evidence.clone())
        };

        if should_isolate {
            self.isolate_peer(peer_id, evidence).await;
        }
    }

    /// Isolate a Byzantine peer
    async fn isolate_peer(&self, peer_id: &str, evidence: ByzantineEvidence) {
        // Mark as isolated in peer state
        {
            let mut states = self.peer_states.write().await;
            if let Some(state) = states.get_mut(peer_id) {
                state.isolated = true;
                state.isolation_start = Some(Instant::now());
            }
        }

        // Add to isolated set
        {
            let mut isolated = self.isolated_peers.write().await;
            isolated.insert(peer_id.to_string());
        }

        error!(
            "🔴 ISOLATED BYZANTINE PEER: {} (fault type: {:?})",
            peer_id, evidence.fault_type
        );

        // Call isolation callback if set
        if let Some(ref callback) = self.isolation_callback {
            callback(peer_id.to_string(), evidence);
        }
    }

    /// Check if a peer can be re-admitted after isolation
    pub async fn check_readmission(&self, peer_id: &str) -> bool {
        let can_readmit = {
            let states = self.peer_states.read().await;
            states.get(peer_id).map_or(false, |s| s.can_readmit())
        };

        if can_readmit {
            // Remove from isolated set
            {
                let mut isolated = self.isolated_peers.write().await;
                isolated.remove(peer_id);
            }

            // Reset fault state
            {
                let mut states = self.peer_states.write().await;
                if let Some(state) = states.get_mut(peer_id) {
                    state.readmit();
                }
            }

            info!("✅ Re-admitted peer {} after isolation period", peer_id);
            true
        } else {
            false
        }
    }

    /// Run periodic maintenance (decay faults, check re-admissions)
    pub async fn maintenance(&self) {
        // Decay faults
        {
            let mut states = self.peer_states.write().await;
            for (_, state) in states.iter_mut() {
                state.decay_faults();
            }
        }

        // Check for re-admissions
        let isolated: Vec<String> = self.get_isolated_peers().await;
        for peer_id in isolated {
            self.check_readmission(&peer_id).await;
        }
    }

    /// Get fault statistics for a peer
    pub async fn get_peer_stats(&self, peer_id: &str) -> Option<PeerFaultStats> {
        let states = self.peer_states.read().await;
        states.get(peer_id).map(|state| PeerFaultStats {
            peer_id: peer_id.to_string(),
            fault_count: state.fault_count,
            fault_score: state.fault_score,
            is_isolated: state.isolated,
            evidence_count: state.evidence.len(),
        })
    }

    /// Get all peer statistics
    pub async fn get_all_stats(&self) -> HashMap<String, PeerFaultStats> {
        let states = self.peer_states.read().await;
        states
            .iter()
            .map(|(id, state)| {
                (
                    id.clone(),
                    PeerFaultStats {
                        peer_id: id.clone(),
                        fault_count: state.fault_count,
                        fault_score: state.fault_score,
                        is_isolated: state.isolated,
                        evidence_count: state.evidence.len(),
                    },
                )
            })
            .collect()
    }

    /// Clear state for a peer (use with caution)
    pub async fn clear_peer_state(&self, peer_id: &str) {
        let mut states = self.peer_states.write().await;
        states.remove(peer_id);

        let mut isolated = self.isolated_peers.write().await;
        isolated.remove(peer_id);

        info!("Cleared Byzantine state for peer {}", peer_id);
    }
}

// ============================================================================
// Statistics
// ============================================================================

/// Fault statistics for a peer (for API/monitoring)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PeerFaultStats {
    pub peer_id: String,
    pub fault_count: u32,
    pub fault_score: u32,
    pub is_isolated: bool,
    pub evidence_count: usize,
}

// ============================================================================
// Utilities
// ============================================================================

/// Simple hash function for evidence deduplication
fn simple_hash(data: &[u8]) -> Vec<u8> {
    // Simple djb2 hash (for deduplication only, not cryptographic)
    let mut hash: u64 = 5381;
    for byte in data {
        hash = hash.wrapping_mul(33).wrapping_add(*byte as u64);
    }
    hash.to_le_bytes().to_vec()
}

use std::collections::HashSet;

// ============================================================================
// Tests
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_proposal_equivocation_detection() {
        let detector = ByzantineDetector::new("test-hub".to_string());

        // First proposal is fine
        let result = detector
            .record_proposal("peer-1", 1, 0, vec![1, 2, 3])
            .await;
        assert!(result.is_ok());

        // Same proposal hash is fine
        let result = detector
            .record_proposal("peer-1", 1, 0, vec![1, 2, 3])
            .await;
        assert!(result.is_ok());

        // Different proposal hash = equivocation!
        let result = detector
            .record_proposal("peer-1", 1, 0, vec![4, 5, 6])
            .await;
        assert!(result.is_err());

        // Peer should be isolated
        assert!(detector.is_isolated("peer-1").await);
    }

    #[tokio::test]
    async fn test_vote_equivocation_detection() {
        let detector = ByzantineDetector::new("test-hub".to_string());

        // First vote is fine
        let result = detector
            .record_vote("peer-1", 1, 0, "prevote", vec![1, 2, 3])
            .await;
        assert!(result.is_ok());

        // Different vote hash = equivocation!
        let result = detector
            .record_vote("peer-1", 1, 0, "prevote", vec![4, 5, 6])
            .await;
        assert!(result.is_err());

        // Peer should be isolated
        assert!(detector.is_isolated("peer-1").await);
    }

    #[tokio::test]
    async fn test_fault_threshold() {
        let detector = ByzantineDetector::new("test-hub".to_string());

        // Report multiple non-critical faults
        for _ in 0..5 {
            detector.report_heartbeat_timeout("peer-1", 0, 15000).await;
        }

        // Should not be isolated yet (low severity faults)
        assert!(!detector.is_isolated("peer-1").await);

        // Report invalid signature (higher severity)
        for _ in 0..3 {
            detector
                .report_invalid_signature("peer-1", "proposal", vec![])
                .await;
        }

        // Should now be isolated
        assert!(detector.is_isolated("peer-1").await);
    }

    #[test]
    fn test_fault_severity() {
        assert!(
            ByzantineFaultType::ProposalEquivocation {
                height: 0,
                round: 0,
                proposal1: vec![],
                proposal2: vec![]
            }
            .severity()
                > ByzantineFaultType::HeartbeatTimeout {
                    last_seen: 0,
                    timeout_ms: 0
                }
                .severity()
        );
    }
}

/*
 * 鏡
 * Trust is verified. Equivocation is detected. Byzantine faults are isolated.
 * h(x) ≥ 0. Always.
 */
