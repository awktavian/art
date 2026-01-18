//! Byzantine Fault Tolerant Leader Election
//!
//! Implements Tendermint-style leader election with:
//! - Proposal round with designated proposer
//! - Pre-vote and pre-commit phases
//! - 2/3+ majority required for consensus
//! - View change on timeout
//! - **Ed25519 signature verification** (Jan 4, 2026)
//! - **Equivocation detection** (Jan 11, 2026)
//! - **View change protocol** (Jan 11, 2026)
//!
//! Architecture:
//! ```
//! ┌─────────────────────────────────────────────────────────────────┐
//! │                  BFT LEADER ELECTION                             │
//! ├─────────────────────────────────────────────────────────────────┤
//! │                                                                  │
//! │   Round r, Height h                                             │
//! │       │                                                         │
//! │       ▼                                                         │
//! │   ┌─────────────────────────────────────────────────────────┐  │
//! │   │              PROPOSER (round-robin)                      │  │
//! │   │                    │                                     │  │
//! │   │             PROPOSE(height, round, value)                │  │
//! │   │                    │                                     │  │
//! │   │                    ▼                                     │  │
//! │   │   PRE-VOTE ──▶ wait for 2/3+ ──▶ PRE-COMMIT             │  │
//! │   │                                       │                  │  │
//! │   │                                       ▼                  │  │
//! │   │                      wait for 2/3+ ──▶ COMMIT            │  │
//! │   └─────────────────────────────────────────────────────────┘  │
//! │                                                                  │
//! │   Timeout ──▶ VIEW-CHANGE ──▶ Round r+1 (new proposer)         │
//! │                                                                  │
//! └─────────────────────────────────────────────────────────────────┘
//! ```
//!
//! Byzantine Safety:
//! - Requires 2f+1 votes (where n=3f+1 validators)
//! - No conflicting decisions at same height
//! - Liveness with eventual synchrony
//! - **Ed25519 signatures prevent message forgery**
//! - **Equivocation detection isolates Byzantine nodes**
//!
//! Colony: Crystal (D₅) — Consensus verification
//!
//! η → s → μ → a → η′
//! h(x) ≥ 0. Always.

use std::collections::{HashMap, HashSet};
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::sync::{mpsc, RwLock, broadcast};
use tracing::{info, warn, error, debug};
use serde::{Deserialize, Serialize};

use super::Peer;
use super::auth::MeshAuth;
use crate::byzantine::{ByzantineDetector, ByzantineEvidence, ByzantineFaultType};

/// Timeout for proposal phase
const PROPOSAL_TIMEOUT: Duration = Duration::from_secs(3);
/// Timeout for pre-vote phase
const PREVOTE_TIMEOUT: Duration = Duration::from_secs(2);
/// Timeout for pre-commit phase
const PRECOMMIT_TIMEOUT: Duration = Duration::from_secs(2);
/// Minimum validators for BFT (3f+1 where f=1)
const MIN_VALIDATORS: usize = 4;
/// View change timeout multiplier (view_change_timeout = base_timeout * VIEW_CHANGE_MULTIPLIER)
const VIEW_CHANGE_MULTIPLIER: u32 = 2;

/// BFT consensus phase
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum Phase {
    /// Waiting for proposal from designated proposer
    NewRound,
    /// Collecting pre-votes
    PreVote,
    /// Collecting pre-commits
    PreCommit,
    /// Consensus reached
    Commit,
    /// Waiting for view change (proposer failed)
    ViewChange,
}

/// Vote type
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum VoteType {
    PreVote,
    PreCommit,
}

/// A proposal for leader election
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Proposal {
    /// Height (election round)
    pub height: u64,
    /// Round within height (for timeouts)
    pub round: u32,
    /// Proposed leader ID
    pub leader_id: String,
    /// Proposer's hub ID
    pub proposer_id: String,
    /// Timestamp
    pub timestamp: u64,
    /// Signature (ed25519)
    pub signature: Vec<u8>,
}

impl Proposal {
    /// Get canonical bytes for signing/verification
    pub fn signable_bytes(&self) -> Vec<u8> {
        format!(
            "{}:{}:{}:{}",
            self.height, self.round, self.leader_id, self.timestamp
        ).into_bytes()
    }

    /// Compute hash for equivocation detection
    pub fn hash(&self) -> Vec<u8> {
        let data = format!(
            "proposal:{}:{}:{}:{}:{}",
            self.height, self.round, self.leader_id, self.proposer_id, self.timestamp
        );
        simple_hash(data.as_bytes())
    }
}

/// A vote (pre-vote or pre-commit)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Vote {
    /// Vote type
    pub vote_type: VoteType,
    /// Height
    pub height: u64,
    /// Round
    pub round: u32,
    /// Voted leader ID (or nil if timeout)
    pub leader_id: Option<String>,
    /// Voter's hub ID
    pub voter_id: String,
    /// Signature
    pub signature: Vec<u8>,
}

impl Vote {
    /// Get canonical bytes for signing/verification
    pub fn signable_bytes(&self) -> Vec<u8> {
        let vote_type_str = match self.vote_type {
            VoteType::PreVote => "prevote",
            VoteType::PreCommit => "precommit",
        };
        format!(
            "{}:{}:{}:{:?}",
            vote_type_str, self.height, self.round, self.leader_id
        ).into_bytes()
    }

    /// Compute hash for equivocation detection
    pub fn hash(&self) -> Vec<u8> {
        let vote_type_str = match self.vote_type {
            VoteType::PreVote => "prevote",
            VoteType::PreCommit => "precommit",
        };
        let data = format!(
            "vote:{}:{}:{}:{:?}:{}",
            vote_type_str, self.height, self.round, self.leader_id, self.voter_id
        );
        simple_hash(data.as_bytes())
    }
}

/// View change request message
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ViewChangeRequest {
    /// Height
    pub height: u64,
    /// Current round (requesting change from)
    pub round: u32,
    /// Sender's hub ID
    pub sender_id: String,
    /// Reason for view change
    pub reason: ViewChangeReason,
    /// Signature
    pub signature: Vec<u8>,
}

impl ViewChangeRequest {
    /// Get canonical bytes for signing/verification
    pub fn signable_bytes(&self) -> Vec<u8> {
        format!(
            "viewchange:{}:{}:{:?}",
            self.height, self.round, self.reason
        ).into_bytes()
    }
}

/// Reason for requesting view change
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ViewChangeReason {
    /// Proposer timed out
    ProposerTimeout,
    /// Proposer sent invalid proposal
    InvalidProposal,
    /// Byzantine behavior detected
    ByzantineBehavior { peer_id: String },
    /// Manual request (admin)
    ManualRequest,
}

/// Message types for BFT consensus
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum BftMessage {
    Proposal(Proposal),
    Vote(Vote),
    /// View change request
    ViewChangeRequest(ViewChangeRequest),
    /// View change acknowledgement
    ViewChangeAck {
        height: u64,
        round: u32,
        sender_id: String,
        signature: Vec<u8>,
    },
    /// Request to sync state
    SyncRequest { from_height: u64 },
    /// Sync response with decided heights
    SyncResponse { decisions: Vec<(u64, String)> },
}

/// Locked value for safety (ensures no conflicting commits)
#[derive(Debug, Clone)]
pub struct LockedValue {
    /// The locked leader ID
    pub leader_id: String,
    /// Round at which we locked
    pub round: u32,
}

/// State of the BFT consensus
#[derive(Debug)]
pub struct BftState {
    /// Current height (election number)
    pub height: u64,
    /// Current round within height
    pub round: u32,
    /// Current phase
    pub phase: Phase,
    /// Current proposal
    pub proposal: Option<Proposal>,
    /// Pre-votes received: (height, round) -> voter_id -> (leader_id, signature)
    pub prevotes: HashMap<(u64, u32), HashMap<String, (Option<String>, Vec<u8>)>>,
    /// Pre-commits received: (height, round) -> voter_id -> (leader_id, signature)
    pub precommits: HashMap<(u64, u32), HashMap<String, (Option<String>, Vec<u8>)>>,
    /// View change requests: (height, round) -> sender_id -> reason
    pub view_change_requests: HashMap<(u64, u32), HashMap<String, ViewChangeReason>>,
    /// Decided leaders by height
    pub decisions: HashMap<u64, String>,
    /// Round start time (for timeouts)
    pub round_start: Instant,
    /// Locked value (for safety across rounds)
    pub locked_value: Option<LockedValue>,
    /// Valid value (proposal we've pre-voted for)
    pub valid_value: Option<String>,
    /// Valid round
    pub valid_round: Option<u32>,
    /// Proposals we've seen at each (height, round) for equivocation detection
    pub seen_proposals: HashMap<(u64, u32), HashMap<String, Vec<u8>>>,
    /// Votes we've seen at each (height, round, vote_type) for equivocation detection
    pub seen_votes: HashMap<(u64, u32, String), HashMap<String, Vec<u8>>>,
}

impl BftState {
    pub fn new() -> Self {
        Self {
            height: 1,
            round: 0,
            phase: Phase::NewRound,
            proposal: None,
            prevotes: HashMap::new(),
            precommits: HashMap::new(),
            view_change_requests: HashMap::new(),
            decisions: HashMap::new(),
            round_start: Instant::now(),
            locked_value: None,
            valid_value: None,
            valid_round: None,
            seen_proposals: HashMap::new(),
            seen_votes: HashMap::new(),
        }
    }

    /// Get total votes for a leader at (height, round)
    pub fn count_prevotes(&self, height: u64, round: u32, leader_id: &Option<String>) -> usize {
        self.prevotes
            .get(&(height, round))
            .map(|votes| votes.values().filter(|(v, _)| v == leader_id).count())
            .unwrap_or(0)
    }

    /// Get total precommits for a leader at (height, round)
    pub fn count_precommits(&self, height: u64, round: u32, leader_id: &Option<String>) -> usize {
        self.precommits
            .get(&(height, round))
            .map(|votes| votes.values().filter(|(v, _)| v == leader_id).count())
            .unwrap_or(0)
    }

    /// Get count of view change requests for (height, round)
    pub fn count_view_change_requests(&self, height: u64, round: u32) -> usize {
        self.view_change_requests
            .get(&(height, round))
            .map(|reqs| reqs.len())
            .unwrap_or(0)
    }

    /// Check for proposal equivocation
    pub fn check_proposal_equivocation(
        &mut self,
        proposer_id: &str,
        height: u64,
        round: u32,
        proposal_hash: Vec<u8>,
    ) -> Option<ByzantineEvidence> {
        let key = (height, round);
        let proposer_proposals = self.seen_proposals.entry(key).or_default();

        if let Some(existing_hash) = proposer_proposals.get(proposer_id) {
            if existing_hash != &proposal_hash {
                // Equivocation detected!
                return Some(ByzantineEvidence::new(
                    proposer_id.to_string(),
                    ByzantineFaultType::ProposalEquivocation {
                        height,
                        round,
                        proposal1: existing_hash.clone(),
                        proposal2: proposal_hash,
                    },
                ));
            }
        } else {
            proposer_proposals.insert(proposer_id.to_string(), proposal_hash);
        }
        None
    }

    /// Check for vote equivocation
    pub fn check_vote_equivocation(
        &mut self,
        voter_id: &str,
        height: u64,
        round: u32,
        vote_type: &str,
        vote_hash: Vec<u8>,
    ) -> Option<ByzantineEvidence> {
        let key = (height, round, vote_type.to_string());
        let voter_votes = self.seen_votes.entry(key).or_default();

        if let Some(existing_hash) = voter_votes.get(voter_id) {
            if existing_hash != &vote_hash {
                // Equivocation detected!
                return Some(ByzantineEvidence::new(
                    voter_id.to_string(),
                    ByzantineFaultType::VoteEquivocation {
                        height,
                        round,
                        vote1: existing_hash.clone(),
                        vote2: vote_hash,
                    },
                ));
            }
        } else {
            voter_votes.insert(voter_id.to_string(), vote_hash);
        }
        None
    }

    /// Clean up old state to prevent memory growth
    pub fn cleanup_old_state(&mut self, current_height: u64) {
        // Keep last 10 heights of history
        let min_height = current_height.saturating_sub(10);

        self.prevotes.retain(|(h, _), _| *h >= min_height);
        self.precommits.retain(|(h, _), _| *h >= min_height);
        self.view_change_requests.retain(|(h, _), _| *h >= min_height);
        self.seen_proposals.retain(|(h, _), _| *h >= min_height);
        self.seen_votes.retain(|(h, _, _), _| *h >= min_height);
        self.decisions.retain(|h, _| *h >= min_height);
    }
}

impl Default for BftState {
    fn default() -> Self {
        Self::new()
    }
}

/// BFT Leader Election with Ed25519 signature verification
pub struct BftLeaderElection {
    /// This hub's ID
    hub_id: String,
    /// Cryptographic authentication (Ed25519 signing/verification)
    auth: Arc<MeshAuth>,
    /// Known peers (validators)
    peers: Arc<RwLock<Vec<Peer>>>,
    /// Consensus state
    state: RwLock<BftState>,
    /// Current leader
    current_leader: RwLock<Option<String>>,
    /// Message sender (to broadcast to peers)
    msg_tx: broadcast::Sender<BftMessage>,
    /// Whether we're running
    running: std::sync::atomic::AtomicBool,
    /// Peer public keys for signature verification (hub_id -> public_key)
    peer_public_keys: RwLock<HashMap<String, Vec<u8>>>,
    /// Byzantine fault detector
    byzantine_detector: Arc<ByzantineDetector>,
    /// Isolated peers (do not accept messages from these)
    isolated_peers: RwLock<HashSet<String>>,
    /// Event channel for consensus events
    event_tx: Option<mpsc::Sender<ConsensusEvent>>,
}

/// Events emitted by consensus
#[derive(Debug, Clone)]
pub enum ConsensusEvent {
    /// New leader elected
    LeaderElected { height: u64, leader_id: String },
    /// Round changed (timeout or view change)
    RoundChanged { height: u64, new_round: u32 },
    /// Byzantine fault detected
    ByzantineFault { peer_id: String, evidence: ByzantineEvidence },
    /// Peer isolated
    PeerIsolated { peer_id: String },
}

impl BftLeaderElection {
    /// Create new BFT leader election with Ed25519 authentication
    pub fn new(
        hub_id: String,
        auth: Arc<MeshAuth>,
        peers: Arc<RwLock<Vec<Peer>>>,
    ) -> (Self, broadcast::Receiver<BftMessage>) {
        let (msg_tx, msg_rx) = broadcast::channel(100);
        let byzantine_detector = Arc::new(ByzantineDetector::new(hub_id.clone()));

        let election = Self {
            hub_id: hub_id.clone(),
            auth,
            peers,
            state: RwLock::new(BftState::new()),
            current_leader: RwLock::new(None),
            msg_tx,
            running: std::sync::atomic::AtomicBool::new(false),
            peer_public_keys: RwLock::new(HashMap::new()),
            byzantine_detector,
            isolated_peers: RwLock::new(HashSet::new()),
            event_tx: None,
        };

        (election, msg_rx)
    }

    /// Create with external Byzantine detector
    pub fn with_byzantine_detector(
        hub_id: String,
        auth: Arc<MeshAuth>,
        peers: Arc<RwLock<Vec<Peer>>>,
        byzantine_detector: Arc<ByzantineDetector>,
    ) -> (Self, broadcast::Receiver<BftMessage>) {
        let (msg_tx, msg_rx) = broadcast::channel(100);

        let election = Self {
            hub_id,
            auth,
            peers,
            state: RwLock::new(BftState::new()),
            current_leader: RwLock::new(None),
            msg_tx,
            running: std::sync::atomic::AtomicBool::new(false),
            peer_public_keys: RwLock::new(HashMap::new()),
            byzantine_detector,
            isolated_peers: RwLock::new(HashSet::new()),
            event_tx: None,
        };

        (election, msg_rx)
    }

    /// Set event channel for consensus events
    pub fn set_event_channel(&mut self, tx: mpsc::Sender<ConsensusEvent>) {
        self.event_tx = Some(tx);
    }

    /// Register a peer's public key for signature verification
    pub async fn register_peer_key(&self, hub_id: &str, public_key: Vec<u8>) {
        let mut keys = self.peer_public_keys.write().await;
        keys.insert(hub_id.to_string(), public_key);
        debug!("Registered public key for peer: {}", hub_id);
    }

    /// Remove a peer's public key (e.g., on Byzantine detection)
    pub async fn unregister_peer_key(&self, hub_id: &str) {
        let mut keys = self.peer_public_keys.write().await;
        keys.remove(hub_id);
        warn!("Unregistered public key for peer: {} (potential Byzantine node)", hub_id);
    }

    /// Get public key for a peer
    async fn get_peer_public_key(&self, hub_id: &str) -> Option<Vec<u8>> {
        let keys = self.peer_public_keys.read().await;
        keys.get(hub_id).cloned()
    }

    /// Check if a peer is isolated
    async fn is_peer_isolated(&self, peer_id: &str) -> bool {
        let isolated = self.isolated_peers.read().await;
        isolated.contains(peer_id)
    }

    /// Isolate a Byzantine peer
    async fn isolate_peer(&self, peer_id: &str, evidence: ByzantineEvidence) {
        {
            let mut isolated = self.isolated_peers.write().await;
            isolated.insert(peer_id.to_string());
        }

        // Remove their public key
        self.unregister_peer_key(peer_id).await;

        error!(
            "🔴 ISOLATED BYZANTINE PEER: {} (fault: {:?})",
            peer_id, evidence.fault_type
        );

        // Emit event
        if let Some(ref tx) = self.event_tx {
            let _ = tx.send(ConsensusEvent::PeerIsolated {
                peer_id: peer_id.to_string(),
            }).await;
            let _ = tx.send(ConsensusEvent::ByzantineFault {
                peer_id: peer_id.to_string(),
                evidence,
            }).await;
        }
    }

    /// Get total validators (including self, excluding isolated)
    async fn validator_count(&self) -> usize {
        let peers = self.peers.read().await;
        let isolated = self.isolated_peers.read().await;
        let active_peers = peers.iter()
            .filter(|p| !isolated.contains(&p.hub_id))
            .count();
        active_peers + 1 // +1 for self
    }

    /// Get quorum size (2f+1 for n=3f+1)
    async fn quorum_size(&self) -> usize {
        let n = self.validator_count().await;
        // 2f+1 where n = 3f+1 → f = (n-1)/3 → quorum = 2*((n-1)/3)+1
        let f = (n.saturating_sub(1)) / 3;
        2 * f + 1
    }

    /// Get f (maximum Byzantine faults tolerated)
    async fn max_faults(&self) -> usize {
        let n = self.validator_count().await;
        (n.saturating_sub(1)) / 3
    }

    /// Get proposer for round (round-robin by sorted hub ID)
    async fn get_proposer(&self, round: u32) -> String {
        let peers = self.peers.read().await;
        let isolated = self.isolated_peers.read().await;

        let mut validators: Vec<String> = peers.iter()
            .filter(|p| !isolated.contains(&p.hub_id))
            .map(|p| p.hub_id.clone())
            .collect();
        validators.push(self.hub_id.clone());
        validators.sort();

        if validators.is_empty() {
            return self.hub_id.clone();
        }

        let idx = (round as usize) % validators.len();
        validators[idx].clone()
    }

    /// Check if we are the proposer for current round
    async fn am_proposer(&self) -> bool {
        let state = self.state.read().await;
        let proposer = self.get_proposer(state.round).await;
        proposer == self.hub_id
    }

    /// Select leader candidate (e.g., lexicographically lowest alive peer)
    async fn select_leader_candidate(&self) -> String {
        let peers = self.peers.read().await;
        let isolated = self.isolated_peers.read().await;

        let mut candidates: Vec<String> = peers.iter()
            .filter(|p| p.is_alive(Duration::from_secs(30)) && !isolated.contains(&p.hub_id))
            .map(|p| p.hub_id.clone())
            .collect();
        candidates.push(self.hub_id.clone());
        candidates.sort();
        candidates.into_iter().next().unwrap_or_else(|| self.hub_id.clone())
    }

    /// Sign data with Ed25519 private key
    fn sign(&self, data: &[u8]) -> Vec<u8> {
        self.auth.sign_message(data)
    }

    /// Verify Ed25519 signature from a peer
    async fn verify_signature_async(&self, data: &[u8], signature: &[u8], peer_hub_id: &str) -> bool {
        // Check if peer is isolated first
        if self.is_peer_isolated(peer_hub_id).await {
            warn!("Rejecting message from isolated peer: {}", peer_hub_id);
            return false;
        }

        // Get peer's public key
        let public_key = match self.get_peer_public_key(peer_hub_id).await {
            Some(pk) => pk,
            None => {
                warn!("Cannot verify signature: no public key registered for peer {}", peer_hub_id);
                return false;
            }
        };

        // Verify using MeshAuth
        let valid = self.auth.verify_peer_signature(data, signature, &public_key);

        if !valid {
            warn!("🔴 Invalid signature from peer {} - potential Byzantine behavior!", peer_hub_id);

            // Report to Byzantine detector
            let _ = self.byzantine_detector.report_invalid_signature(
                peer_hub_id,
                "consensus_message",
                simple_hash(data),
            ).await;
        }

        valid
    }

    /// Get this hub's public key bytes for sharing with peers
    pub fn public_key_bytes(&self) -> Vec<u8> {
        self.auth.public_key_bytes()
    }

    /// Broadcast message to all peers
    fn broadcast(&self, msg: BftMessage) {
        let _ = self.msg_tx.send(msg);
    }

    /// Emit a consensus event
    async fn emit_event(&self, event: ConsensusEvent) {
        if let Some(ref tx) = self.event_tx {
            let _ = tx.send(event).await;
        }
    }

    /// Start consensus round
    pub async fn start_round(&self) {
        let mut state = self.state.write().await;
        state.round_start = Instant::now();
        state.phase = Phase::NewRound;
        state.proposal = None;

        let height = state.height;
        let round = state.round;

        info!("📋 Starting BFT round h={} r={}", height, round);

        // Initialize vote maps for this round
        state.prevotes.entry((height, round)).or_default();
        state.precommits.entry((height, round)).or_default();
        state.view_change_requests.entry((height, round)).or_default();

        // Cleanup old state periodically
        if round == 0 {
            state.cleanup_old_state(height);
        }
    }

    /// Make proposal if we are the proposer
    pub async fn maybe_propose(&self) {
        if !self.am_proposer().await {
            return;
        }

        let (height, round, maybe_leader_id) = {
            let state = self.state.read().await;
            if state.phase != Phase::NewRound {
                return;
            }

            let height = state.height;
            let round = state.round;

            // If we have a locked value, we must propose that
            let leader_id = if let Some(ref locked) = state.locked_value {
                Some(locked.leader_id.clone())
            } else if let Some(ref valid) = state.valid_value {
                // Prefer valid value if we have one
                Some(valid.clone())
            } else {
                None
            };

            (height, round, leader_id)
        };

        // If we didn't have a locked/valid value, select a candidate
        let leader_id = match maybe_leader_id {
            Some(id) => id,
            None => self.select_leader_candidate().await,
        };

        let timestamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();

        let proposal_data = format!("{}:{}:{}:{}", height, round, leader_id, timestamp);
        let signature = self.sign(proposal_data.as_bytes());

        let proposal = Proposal {
            height,
            round,
            leader_id: leader_id.clone(),
            proposer_id: self.hub_id.clone(),
            timestamp,
            signature,
        };

        info!("📣 Proposing leader: {} (h={} r={})", leader_id, height, round);

        // Store and broadcast
        {
            let mut state = self.state.write().await;
            state.proposal = Some(proposal.clone());
            state.phase = Phase::PreVote;
        }

        self.broadcast(BftMessage::Proposal(proposal));

        // Also send our pre-vote
        self.send_prevote(Some(leader_id)).await;
    }

    /// Handle received proposal with Ed25519 signature verification and equivocation detection
    pub async fn handle_proposal(&self, proposal: Proposal) {
        // 0. Check if proposer is isolated
        if self.is_peer_isolated(&proposal.proposer_id).await {
            warn!("Ignoring proposal from isolated peer: {}", proposal.proposer_id);
            return;
        }

        // 1. Verify Ed25519 signature FIRST (Byzantine protection)
        if !self.verify_signature_async(
            &proposal.signable_bytes(),
            &proposal.signature,
            &proposal.proposer_id,
        ).await {
            error!(
                "🔴 BYZANTINE: Invalid signature on proposal from {} - REJECTING",
                proposal.proposer_id
            );
            return;
        }

        // 2. Check for equivocation
        let proposal_hash = proposal.hash();
        {
            let mut state = self.state.write().await;
            if let Some(evidence) = state.check_proposal_equivocation(
                &proposal.proposer_id,
                proposal.height,
                proposal.round,
                proposal_hash,
            ) {
                error!(
                    "🔴 EQUIVOCATION: Peer {} sent conflicting proposals for h={} r={}",
                    proposal.proposer_id, proposal.height, proposal.round
                );
                drop(state);
                self.isolate_peer(&proposal.proposer_id, evidence).await;
                return;
            }
        }

        let mut state = self.state.write().await;

        // 3. Validate height/round
        if proposal.height != state.height {
            debug!("Ignoring proposal for different height");
            return;
        }

        if proposal.round < state.round {
            debug!("Ignoring proposal for old round");
            return;
        }

        if proposal.round > state.round {
            // Future round - might indicate we need to catch up
            debug!("Received proposal for future round, may need sync");
            return;
        }

        // 4. Validate proposer is expected for this round
        let expected_proposer = self.get_proposer(state.round).await;
        if proposal.proposer_id != expected_proposer {
            warn!(
                "Invalid proposer: {} (expected {}) - potential Byzantine behavior",
                proposal.proposer_id, expected_proposer
            );

            // Report invalid leader proposal
            let evidence = ByzantineEvidence::new(
                proposal.proposer_id.clone(),
                ByzantineFaultType::InvalidLeaderProposal {
                    proposed_leader: proposal.leader_id.clone(),
                    reason: format!("Unexpected proposer for round {}", state.round),
                },
            );
            drop(state);
            self.byzantine_detector.report_invalid_signature(
                &proposal.proposer_id,
                "proposal",
                simple_hash(b"wrong_proposer"),
            ).await;
            return;
        }

        // 5. Check phase
        if state.phase != Phase::NewRound && state.phase != Phase::ViewChange {
            debug!("Already have proposal for this round");
            return;
        }

        info!(
            "📨 ✓ Verified proposal from {}: leader={} (signature valid)",
            proposal.proposer_id, proposal.leader_id
        );

        // 6. Decide whether to accept proposal based on locked value
        let should_accept = if let Some(ref locked) = state.locked_value {
            // We have a locked value - only accept if proposal matches or is from higher POL round
            proposal.leader_id == locked.leader_id
        } else {
            true
        };

        if !should_accept {
            debug!("Rejecting proposal - conflicts with locked value");
            drop(state);
            self.send_prevote(None).await;
            return;
        }

        state.proposal = Some(proposal.clone());
        state.phase = Phase::PreVote;
        drop(state);

        // Send our pre-vote
        self.send_prevote(Some(proposal.leader_id)).await;
    }

    /// Send pre-vote
    async fn send_prevote(&self, leader_id: Option<String>) {
        let state = self.state.read().await;
        let height = state.height;
        let round = state.round;
        drop(state);

        let vote_data = format!("prevote:{}:{}:{:?}", height, round, leader_id);
        let signature = self.sign(vote_data.as_bytes());

        let vote = Vote {
            vote_type: VoteType::PreVote,
            height,
            round,
            leader_id: leader_id.clone(),
            voter_id: self.hub_id.clone(),
            signature,
        };

        debug!("🗳️ Sending pre-vote for {:?}", leader_id);

        // Store own vote
        {
            let mut state = self.state.write().await;
            state.prevotes
                .entry((height, round))
                .or_default()
                .insert(self.hub_id.clone(), (leader_id, vote.signature.clone()));
        }

        self.broadcast(BftMessage::Vote(vote));

        // Check if we have quorum
        self.check_prevote_quorum().await;
    }

    /// Handle received vote with Ed25519 signature verification and equivocation detection
    pub async fn handle_vote(&self, vote: Vote) {
        // 0. Check if voter is isolated
        if self.is_peer_isolated(&vote.voter_id).await {
            warn!("Ignoring vote from isolated peer: {}", vote.voter_id);
            return;
        }

        // 1. Verify Ed25519 signature FIRST (Byzantine protection)
        if !self.verify_signature_async(
            &vote.signable_bytes(),
            &vote.signature,
            &vote.voter_id,
        ).await {
            error!(
                "🔴 BYZANTINE: Invalid signature on {:?} from {} - REJECTING",
                vote.vote_type, vote.voter_id
            );
            return;
        }

        // 2. Check for equivocation
        let vote_type_str = match vote.vote_type {
            VoteType::PreVote => "prevote",
            VoteType::PreCommit => "precommit",
        };
        let vote_hash = vote.hash();

        {
            let mut state = self.state.write().await;
            if let Some(evidence) = state.check_vote_equivocation(
                &vote.voter_id,
                vote.height,
                vote.round,
                vote_type_str,
                vote_hash,
            ) {
                error!(
                    "🔴 EQUIVOCATION: Peer {} sent conflicting {} votes for h={} r={}",
                    vote.voter_id, vote_type_str, vote.height, vote.round
                );
                drop(state);
                self.isolate_peer(&vote.voter_id, evidence).await;
                return;
            }
        }

        let mut state = self.state.write().await;

        // 3. Validate height
        if vote.height != state.height {
            return;
        }

        // 4. Record verified vote
        match vote.vote_type {
            VoteType::PreVote => {
                state.prevotes
                    .entry((vote.height, vote.round))
                    .or_default()
                    .insert(vote.voter_id.clone(), (vote.leader_id.clone(), vote.signature.clone()));

                debug!(
                    "✓ Verified pre-vote from {} for {:?} (h={} r={})",
                    vote.voter_id, vote.leader_id, vote.height, vote.round
                );
            }
            VoteType::PreCommit => {
                state.precommits
                    .entry((vote.height, vote.round))
                    .or_default()
                    .insert(vote.voter_id.clone(), (vote.leader_id.clone(), vote.signature.clone()));

                debug!(
                    "✓ Verified pre-commit from {} for {:?} (h={} r={})",
                    vote.voter_id, vote.leader_id, vote.height, vote.round
                );
            }
        }

        drop(state);

        // Check quorums
        match vote.vote_type {
            VoteType::PreVote => self.check_prevote_quorum().await,
            VoteType::PreCommit => self.check_precommit_quorum().await,
        }
    }

    /// Check if we have 2/3+ pre-votes for a leader
    async fn check_prevote_quorum(&self) {
        let quorum = self.quorum_size().await;
        let mut state = self.state.write().await;

        if state.phase != Phase::PreVote {
            return;
        }

        let height = state.height;
        let round = state.round;

        // Count votes for each leader
        let votes = match state.prevotes.get(&(height, round)) {
            Some(v) => v,
            None => return,
        };

        let mut counts: HashMap<Option<String>, usize> = HashMap::new();
        for (leader_id, _) in votes.values() {
            *counts.entry(leader_id.clone()).or_default() += 1;
        }

        // Check for quorum - first check nil votes
        let nil_count = counts.get(&None).copied().unwrap_or(0);

        // Check for quorum on actual leaders
        for (leader_id, count) in &counts {
            if *count >= quorum {
                if let Some(leader) = leader_id {
                    info!("🔒 Pre-vote quorum reached for {:?} ({}/{})", leader_id, count, quorum);

                    // Update valid value (for future rounds)
                    state.valid_value = Some(leader.clone());
                    state.valid_round = Some(round);

                    state.phase = Phase::PreCommit;
                    let leader_id_clone = leader_id.clone();
                    drop(state);

                    // Send pre-commit
                    self.send_precommit(leader_id_clone).await;
                    return;
                }
            }
        }

        // Check for nil quorum (need to move to next round)
        if nil_count >= quorum {
            info!("🔒 Nil pre-vote quorum reached ({}/{}), moving to pre-commit nil", nil_count, quorum);
            state.phase = Phase::PreCommit;
            drop(state);
            self.send_precommit(None).await;
        }
    }

    /// Send pre-commit
    async fn send_precommit(&self, leader_id: Option<String>) {
        let state = self.state.read().await;
        let height = state.height;
        let round = state.round;
        drop(state);

        let vote_data = format!("precommit:{}:{}:{:?}", height, round, leader_id);
        let signature = self.sign(vote_data.as_bytes());

        let vote = Vote {
            vote_type: VoteType::PreCommit,
            height,
            round,
            leader_id: leader_id.clone(),
            voter_id: self.hub_id.clone(),
            signature,
        };

        debug!("🗳️ Sending pre-commit for {:?}", leader_id);

        // If we're pre-committing for a value, lock it
        {
            let mut state = self.state.write().await;
            if let Some(ref leader) = leader_id {
                state.locked_value = Some(LockedValue {
                    leader_id: leader.clone(),
                    round,
                });
            }

            state.precommits
                .entry((height, round))
                .or_default()
                .insert(self.hub_id.clone(), (leader_id, vote.signature.clone()));
        }

        self.broadcast(BftMessage::Vote(vote));

        // Check if we have quorum
        self.check_precommit_quorum().await;
    }

    /// Check if we have 2/3+ pre-commits for a leader
    async fn check_precommit_quorum(&self) {
        let quorum = self.quorum_size().await;
        let mut state = self.state.write().await;

        if state.phase != Phase::PreCommit {
            return;
        }

        let height = state.height;
        let round = state.round;

        // Count votes
        let votes = match state.precommits.get(&(height, round)) {
            Some(v) => v,
            None => return,
        };

        let mut counts: HashMap<Option<String>, usize> = HashMap::new();
        for (leader_id, _) in votes.values() {
            *counts.entry(leader_id.clone()).or_default() += 1;
        }

        // Check for quorum
        for (leader_id, count) in &counts {
            if *count >= quorum {
                if let Some(leader) = leader_id {
                    info!("✅ BFT CONSENSUS: Leader = {} (h={} r={})", leader, height, round);

                    // Record decision
                    state.decisions.insert(height, leader.clone());
                    state.phase = Phase::Commit;

                    // Clear locked value (we committed)
                    state.locked_value = None;
                    state.valid_value = None;
                    state.valid_round = None;

                    // Move to next height
                    state.height += 1;
                    state.round = 0;

                    let elected_leader = leader.clone();
                    drop(state);

                    // Update current leader
                    *self.current_leader.write().await = Some(elected_leader.clone());

                    // Emit event
                    self.emit_event(ConsensusEvent::LeaderElected {
                        height,
                        leader_id: elected_leader,
                    }).await;

                    // Start next round
                    self.start_round().await;
                    return;
                }
            }
        }

        // Check for nil quorum (need view change)
        let nil_count = counts.get(&None).copied().unwrap_or(0);
        if nil_count >= quorum {
            info!("🔒 Nil pre-commit quorum reached, triggering view change");
            drop(state);
            self.trigger_view_change(ViewChangeReason::ProposerTimeout).await;
        }
    }

    /// Request view change
    pub async fn request_view_change(&self, reason: ViewChangeReason) {
        let state = self.state.read().await;
        let height = state.height;
        let round = state.round;
        drop(state);

        let vc_data = format!("viewchange:{}:{}:{:?}", height, round, reason);
        let signature = self.sign(vc_data.as_bytes());

        let request = ViewChangeRequest {
            height,
            round,
            sender_id: self.hub_id.clone(),
            reason: reason.clone(),
            signature,
        };

        info!("📢 Requesting view change h={} r={} reason={:?}", height, round, reason);

        // Store our request
        {
            let mut state = self.state.write().await;
            state.view_change_requests
                .entry((height, round))
                .or_default()
                .insert(self.hub_id.clone(), reason);
        }

        self.broadcast(BftMessage::ViewChangeRequest(request));

        // Check if we have enough view change requests
        self.check_view_change_quorum().await;
    }

    /// Handle view change request
    pub async fn handle_view_change_request(&self, request: ViewChangeRequest) {
        // 0. Check if sender is isolated
        if self.is_peer_isolated(&request.sender_id).await {
            warn!("Ignoring view change from isolated peer: {}", request.sender_id);
            return;
        }

        // 1. Verify signature
        if !self.verify_signature_async(
            &request.signable_bytes(),
            &request.signature,
            &request.sender_id,
        ).await {
            error!("🔴 Invalid signature on view change request from {}", request.sender_id);
            return;
        }

        let mut state = self.state.write().await;

        // 2. Validate height/round
        if request.height != state.height || request.round != state.round {
            return;
        }

        // 3. Store request
        state.view_change_requests
            .entry((request.height, request.round))
            .or_default()
            .insert(request.sender_id.clone(), request.reason.clone());

        debug!("Received view change request from {} for h={} r={}",
               request.sender_id, request.height, request.round);

        drop(state);

        // Check quorum
        self.check_view_change_quorum().await;
    }

    /// Check if we have f+1 view change requests (sufficient to trigger view change)
    async fn check_view_change_quorum(&self) {
        let f = self.max_faults().await;
        let state = self.state.read().await;

        let height = state.height;
        let round = state.round;

        let vc_count = state.count_view_change_requests(height, round);

        // f+1 view change requests triggers view change
        if vc_count > f {
            drop(state);
            info!("📢 View change quorum reached ({} > f={}), advancing round", vc_count, f);
            self.advance_round().await;
        }
    }

    /// Trigger view change (internal)
    async fn trigger_view_change(&self, reason: ViewChangeReason) {
        {
            let mut state = self.state.write().await;
            state.phase = Phase::ViewChange;
        }

        self.request_view_change(reason).await;
    }

    /// Advance to next round
    ///
    /// Note: This method uses Box::pin for the recursive call to maybe_propose()
    /// to break the async recursion cycle and satisfy Rust's type system.
    /// The cycle is: maybe_propose -> ... -> trigger_view_change -> request_view_change
    ///            -> check_view_change_quorum -> advance_round -> maybe_propose
    fn advance_round(&self) -> std::pin::Pin<Box<dyn std::future::Future<Output = ()> + Send + '_>> {
        Box::pin(async move {
            let new_round = {
                let mut state = self.state.write().await;
                state.round += 1;
                state.phase = Phase::NewRound;
                state.proposal = None;
                state.round_start = Instant::now();
                state.round
            };

            let height = self.state.read().await.height;

            info!("⏭️ Advanced to round {} at height {}", new_round, height);

            self.emit_event(ConsensusEvent::RoundChanged {
                height,
                new_round,
            }).await;

            // Start new round
            self.start_round().await;
            self.maybe_propose().await;
        })
    }

    /// Check for timeouts and trigger round change
    pub async fn check_timeout(&self) {
        let mut state = self.state.write().await;
        let elapsed = state.round_start.elapsed();

        let timeout = match state.phase {
            Phase::NewRound => PROPOSAL_TIMEOUT,
            Phase::PreVote => PREVOTE_TIMEOUT,
            Phase::PreCommit => PRECOMMIT_TIMEOUT,
            Phase::Commit => return,
            Phase::ViewChange => PROPOSAL_TIMEOUT * VIEW_CHANGE_MULTIPLIER,
        };

        if elapsed > timeout {
            let phase = state.phase;
            let height = state.height;
            let round = state.round;
            drop(state);

            warn!("⏱️ Timeout in {:?} phase at h={} r={}", phase, height, round);

            match phase {
                Phase::NewRound => {
                    // Proposer failed - request view change
                    self.trigger_view_change(ViewChangeReason::ProposerTimeout).await;
                }
                Phase::PreVote | Phase::PreCommit => {
                    // Not enough votes - trigger view change
                    self.trigger_view_change(ViewChangeReason::ProposerTimeout).await;
                }
                Phase::ViewChange => {
                    // View change itself timed out - force advance
                    self.advance_round().await;
                }
                Phase::Commit => {}
            }
        }
    }

    /// Get current leader
    pub async fn get_leader(&self) -> Option<String> {
        self.current_leader.read().await.clone()
    }

    /// Check if we are the leader
    pub async fn is_leader(&self) -> bool {
        let leader = self.current_leader.read().await;
        leader.as_ref() == Some(&self.hub_id)
    }

    /// Get consensus state for API
    pub async fn get_state(&self) -> BftConsensusState {
        let state = self.state.read().await;
        let leader = self.current_leader.read().await;
        let validators = self.validator_count().await;
        let isolated = self.isolated_peers.read().await;

        BftConsensusState {
            hub_id: self.hub_id.clone(),
            is_leader: leader.as_ref() == Some(&self.hub_id),
            current_leader: leader.clone(),
            height: state.height,
            round: state.round,
            phase: state.phase,
            validator_count: validators,
            quorum_size: self.quorum_size().await,
            decisions_count: state.decisions.len(),
            isolated_peers: isolated.iter().cloned().collect(),
            locked_value: state.locked_value.as_ref().map(|l| l.leader_id.clone()),
        }
    }

    /// Handle incoming BFT message
    pub async fn handle_message(&self, msg: BftMessage) {
        match msg {
            BftMessage::Proposal(p) => self.handle_proposal(p).await,
            BftMessage::Vote(v) => self.handle_vote(v).await,
            BftMessage::ViewChangeRequest(vc) => self.handle_view_change_request(vc).await,
            BftMessage::ViewChangeAck { height, round, sender_id, signature } => {
                // Verify and handle view change ack
                let data = format!("viewchangeack:{}:{}", height, round);
                if self.verify_signature_async(data.as_bytes(), &signature, &sender_id).await {
                    debug!("Received view change ack from {}", sender_id);
                }
            }
            BftMessage::SyncRequest { from_height } => {
                // Send our decisions
                let state = self.state.read().await;
                let decisions: Vec<(u64, String)> = state.decisions
                    .iter()
                    .filter(|(h, _)| **h >= from_height)
                    .map(|(h, l)| (*h, l.clone()))
                    .collect();

                self.broadcast(BftMessage::SyncResponse { decisions });
            }
            BftMessage::SyncResponse { decisions } => {
                let mut state = self.state.write().await;
                for (height, leader) in decisions {
                    if !state.decisions.contains_key(&height) {
                        state.decisions.insert(height, leader);
                    }
                }
            }
        }
    }

    /// Run the consensus loop
    pub async fn run(&self, mut shutdown: tokio::sync::broadcast::Receiver<()>) {
        self.running.store(true, std::sync::atomic::Ordering::SeqCst);

        info!("🚀 Starting BFT consensus for hub: {}", self.hub_id);

        // Start first round
        self.start_round().await;

        // Main loop
        loop {
            tokio::select! {
                _ = shutdown.recv() => {
                    info!("BFT consensus shutting down");
                    break;
                }
                _ = tokio::time::sleep(Duration::from_millis(100)) => {
                    // Maybe propose if we're the proposer
                    self.maybe_propose().await;

                    // Check for timeouts
                    self.check_timeout().await;
                }
            }
        }

        self.running.store(false, std::sync::atomic::Ordering::SeqCst);
    }

    /// Check if consensus is running
    pub fn is_running(&self) -> bool {
        self.running.load(std::sync::atomic::Ordering::SeqCst)
    }
}

/// BFT consensus state for API responses
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BftConsensusState {
    pub hub_id: String,
    pub is_leader: bool,
    pub current_leader: Option<String>,
    pub height: u64,
    pub round: u32,
    pub phase: Phase,
    pub validator_count: usize,
    pub quorum_size: usize,
    pub decisions_count: usize,
    pub isolated_peers: Vec<String>,
    pub locked_value: Option<String>,
}

/// Simple hash function for equivocation detection (djb2)
fn simple_hash(data: &[u8]) -> Vec<u8> {
    let mut hash: u64 = 5381;
    for byte in data {
        hash = hash.wrapping_mul(33).wrapping_add(*byte as u64);
    }
    hash.to_le_bytes().to_vec()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn create_test_peer(hub_id: &str, port: u16) -> super::super::Peer {
        super::super::Peer {
            hub_id: hub_id.to_string(),
            name: format!("Hub {}", hub_id),
            address: "127.0.0.1".to_string(),
            port,
            last_seen: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_secs(),
            is_leader: false,
            public_key: None,
            tls_enabled: true,
            properties: std::collections::HashMap::new(),
        }
    }

    #[tokio::test]
    async fn test_quorum_calculation() {
        // Create election with 3 peers (4 total validators)
        let peers = Arc::new(RwLock::new(vec![
            create_test_peer("hub-2", 8081),
            create_test_peer("hub-3", 8082),
            create_test_peer("hub-4", 8083),
        ]));

        // Create MeshAuth for signing/verification
        let auth = Arc::new(MeshAuth::new());

        let (election, _rx) = BftLeaderElection::new(
            "hub-1".to_string(),
            auth,
            peers,
        );

        // 4 validators, f=1, quorum=2f+1=3
        assert_eq!(election.validator_count().await, 4);
        assert_eq!(election.quorum_size().await, 3);
        assert_eq!(election.max_faults().await, 1);
    }

    #[tokio::test]
    async fn test_proposer_rotation() {
        let peers = Arc::new(RwLock::new(vec![
            create_test_peer("hub-2", 8081),
            create_test_peer("hub-3", 8082),
        ]));

        let auth = Arc::new(MeshAuth::new());
        let (election, _rx) = BftLeaderElection::new(
            "hub-1".to_string(),
            auth,
            peers,
        );

        // Proposers should rotate deterministically
        let p0 = election.get_proposer(0).await;
        let p1 = election.get_proposer(1).await;
        let p2 = election.get_proposer(2).await;
        let p3 = election.get_proposer(3).await;

        // After 3 rounds, should cycle back
        assert_eq!(p0, p3);
        // All three should be different (round-robin)
        assert!(p0 != p1 || p1 != p2);
    }

    #[tokio::test]
    async fn test_equivocation_detection() {
        let mut state = BftState::new();

        // First proposal is fine
        let result = state.check_proposal_equivocation(
            "peer-1",
            1,
            0,
            vec![1, 2, 3],
        );
        assert!(result.is_none());

        // Same hash is fine
        let result = state.check_proposal_equivocation(
            "peer-1",
            1,
            0,
            vec![1, 2, 3],
        );
        assert!(result.is_none());

        // Different hash = equivocation!
        let result = state.check_proposal_equivocation(
            "peer-1",
            1,
            0,
            vec![4, 5, 6],
        );
        assert!(result.is_some());
    }

    #[tokio::test]
    async fn test_vote_equivocation_detection() {
        let mut state = BftState::new();

        // First vote is fine
        let result = state.check_vote_equivocation(
            "peer-1",
            1,
            0,
            "prevote",
            vec![1, 2, 3],
        );
        assert!(result.is_none());

        // Different hash = equivocation!
        let result = state.check_vote_equivocation(
            "peer-1",
            1,
            0,
            "prevote",
            vec![4, 5, 6],
        );
        assert!(result.is_some());
    }

    #[tokio::test]
    async fn test_locked_value() {
        let mut state = BftState::new();

        // Lock a value
        state.locked_value = Some(LockedValue {
            leader_id: "leader-1".to_string(),
            round: 0,
        });

        assert!(state.locked_value.is_some());
        assert_eq!(state.locked_value.as_ref().unwrap().leader_id, "leader-1");
    }

    #[tokio::test]
    async fn test_view_change_counting() {
        let mut state = BftState::new();

        // Add view change requests
        state.view_change_requests
            .entry((1, 0))
            .or_default()
            .insert("peer-1".to_string(), ViewChangeReason::ProposerTimeout);

        state.view_change_requests
            .entry((1, 0))
            .or_default()
            .insert("peer-2".to_string(), ViewChangeReason::ProposerTimeout);

        assert_eq!(state.count_view_change_requests(1, 0), 2);
        assert_eq!(state.count_view_change_requests(1, 1), 0);
    }

    #[cfg(feature = "mesh")]
    #[tokio::test]
    async fn test_signature_verification() {
        let peers = Arc::new(RwLock::new(vec![]));

        // Create two nodes with their own auth
        let auth1 = Arc::new(MeshAuth::new());
        let auth2 = Arc::new(MeshAuth::new());

        let (election, _rx) = BftLeaderElection::new(
            "hub-1".to_string(),
            auth1.clone(),
            peers.clone(),
        );

        // Register hub-2's public key
        election.register_peer_key("hub-2", auth2.public_key_bytes()).await;

        // Create a message signed by hub-2
        let message = b"test message";
        let signature = auth2.sign_message(message);

        // Verify should succeed
        let valid = election.verify_signature_async(message, &signature, "hub-2").await;
        assert!(valid, "Valid signature should verify");

        // Tampered message should fail
        let tampered = b"tampered message";
        let invalid = election.verify_signature_async(tampered, &signature, "hub-2").await;
        assert!(!invalid, "Tampered message should fail verification");

        // Unknown peer should fail
        let unknown = election.verify_signature_async(message, &signature, "unknown-hub").await;
        assert!(!unknown, "Unknown peer should fail verification");
    }

    #[cfg(feature = "mesh")]
    #[tokio::test]
    async fn test_peer_key_management() {
        let peers = Arc::new(RwLock::new(vec![]));
        let auth = Arc::new(MeshAuth::new());

        let (election, _rx) = BftLeaderElection::new(
            "hub-1".to_string(),
            auth,
            peers,
        );

        // Initially no keys
        assert!(election.get_peer_public_key("hub-2").await.is_none());

        // Register a key
        let key = vec![1u8; 32];
        election.register_peer_key("hub-2", key.clone()).await;

        // Should be retrievable
        let retrieved = election.get_peer_public_key("hub-2").await;
        assert_eq!(retrieved, Some(key));

        // Unregister
        election.unregister_peer_key("hub-2").await;
        assert!(election.get_peer_public_key("hub-2").await.is_none());
    }

    #[tokio::test]
    async fn test_peer_isolation() {
        let peers = Arc::new(RwLock::new(vec![]));
        let auth = Arc::new(MeshAuth::new());

        let (election, _rx) = BftLeaderElection::new(
            "hub-1".to_string(),
            auth,
            peers,
        );

        // Peer not isolated initially
        assert!(!election.is_peer_isolated("bad-peer").await);

        // Isolate peer
        let evidence = ByzantineEvidence::new(
            "bad-peer".to_string(),
            ByzantineFaultType::ProposalEquivocation {
                height: 1,
                round: 0,
                proposal1: vec![1, 2, 3],
                proposal2: vec![4, 5, 6],
            },
        );
        election.isolate_peer("bad-peer", evidence).await;

        // Now isolated
        assert!(election.is_peer_isolated("bad-peer").await);
    }

    #[tokio::test]
    async fn test_state_cleanup() {
        let mut state = BftState::new();
        state.height = 100;

        // Add some old data
        for h in 50..100 {
            state.prevotes.insert((h, 0), HashMap::new());
            state.decisions.insert(h, format!("leader-{}", h));
        }

        // Cleanup
        state.cleanup_old_state(100);

        // Old data should be removed
        assert!(!state.prevotes.contains_key(&(50, 0)));
        assert!(!state.decisions.contains_key(&50));

        // Recent data should remain
        assert!(state.prevotes.contains_key(&(95, 0)));
        assert!(state.decisions.contains_key(&95));
    }

    #[tokio::test]
    async fn test_phase_transitions() {
        let mut state = BftState::new();

        assert_eq!(state.phase, Phase::NewRound);

        state.phase = Phase::PreVote;
        assert_eq!(state.phase, Phase::PreVote);

        state.phase = Phase::PreCommit;
        assert_eq!(state.phase, Phase::PreCommit);

        state.phase = Phase::Commit;
        assert_eq!(state.phase, Phase::Commit);
    }

    #[test]
    fn test_proposal_signable_bytes() {
        let proposal = Proposal {
            height: 1,
            round: 0,
            leader_id: "leader".to_string(),
            proposer_id: "proposer".to_string(),
            timestamp: 12345,
            signature: vec![],
        };

        let bytes = proposal.signable_bytes();
        assert_eq!(bytes, b"1:0:leader:12345");
    }

    #[test]
    fn test_vote_signable_bytes() {
        let vote = Vote {
            vote_type: VoteType::PreVote,
            height: 1,
            round: 0,
            leader_id: Some("leader".to_string()),
            voter_id: "voter".to_string(),
            signature: vec![],
        };

        let bytes = vote.signable_bytes();
        assert!(bytes.starts_with(b"prevote:1:0:"));
    }
}

/*
 * 鏡
 * Byzantine consensus: trust no one, verify everything.
 * 2/3+ agree = truth.
 * Equivocators are isolated. The honest prevail.
 */
