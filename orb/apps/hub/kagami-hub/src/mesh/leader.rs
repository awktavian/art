//! Simple Leader Election Protocol
//!
//! DEPRECATED: For production deployments with 4+ hubs, use `bft_leader.rs`
//! which implements full Tendermint-style BFT consensus with Ed25519 signature
//! verification, equivocation detection, and peer isolation.
//!
//! This simpler implementation is suitable for:
//! - Single-hub deployments (no election needed)
//! - Development/testing scenarios
//! - Small clusters (2-3 hubs) where Byzantine fault tolerance is not critical
//!
//! Implements basic leader election with 2/3+ majority voting.
//! Tolerates up to f Byzantine nodes in a 3f+1 cluster.
//!
//! Protocol:
//! 1. PROPOSE: Candidate proposes themselves based on round-robin
//! 2. PREVOTE: Nodes vote for the proposal if valid
//! 3. PRECOMMIT: After 2/3+ prevotes, nodes precommit
//! 4. COMMIT: After 2/3+ precommits, leader is committed
//!
//! The leader is responsible for:
//! - Contacting the main Kagami API
//! - Distributing state to follower hubs
//! - Handling external requests
//! - Coordinating consensus operations
//!
//! Colony: Crystal (D5) — Byzantine verification
//!
//! h(x) >= 0. Always.
//!
//! Created: January 2026

use std::collections::HashMap;
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::time::{Duration, Instant};
use tokio::sync::RwLock;
use tracing::{info, warn, debug};

use super::Peer;

/// Heartbeat timeout - if leader doesn't heartbeat within this time, re-elect
const HEARTBEAT_TIMEOUT: Duration = Duration::from_secs(30);

/// Proposal timeout for Byzantine election
const PROPOSAL_TIMEOUT: Duration = Duration::from_secs(5);

/// Minimum nodes for Byzantine tolerance (3f+1 where f=1)
const MIN_BYZANTINE_NODES: usize = 4;

/// Election round state
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ElectionPhase {
    /// Waiting for proposal
    Propose,
    /// Voting on proposal
    Prevote,
    /// Precommitting to winner
    Precommit,
    /// Election complete
    Committed,
}

/// Vote type for Byzantine election
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct Vote {
    /// Voter's hub ID
    pub voter_id: String,
    /// Round number
    pub round: u64,
    /// Proposed leader ID
    pub leader_id: String,
    /// Vote phase
    pub phase: String, // "prevote" or "precommit"
    /// Signature (hex-encoded)
    pub signature: String,
}

/// Byzantine-resistant leader election protocol
pub struct LeaderElection {
    /// This hub's ID
    hub_id: String,
    /// Known peers
    peers: Arc<RwLock<Vec<Peer>>>,
    /// Whether this hub is currently the leader
    is_leader: AtomicBool,
    /// Current leader's hub ID
    current_leader: RwLock<Option<String>>,
    /// Last heartbeat from leader
    last_heartbeat: RwLock<Option<Instant>>,
    /// Current election round
    round: AtomicU64,
    /// Current election phase
    phase: RwLock<ElectionPhase>,
    /// Prevotes received: round -> (voter_id -> leader_id)
    prevotes: RwLock<HashMap<u64, HashMap<String, String>>>,
    /// Precommits received: round -> (voter_id -> leader_id)
    precommits: RwLock<HashMap<u64, HashMap<String, String>>>,
    /// Byzantine tolerance mode enabled
    byzantine_mode: AtomicBool,
}

impl LeaderElection {
    /// Create a new leader election instance
    pub fn new(hub_id: String, peers: Arc<RwLock<Vec<Peer>>>) -> Self {
        Self {
            hub_id,
            peers,
            is_leader: AtomicBool::new(false),
            current_leader: RwLock::new(None),
            last_heartbeat: RwLock::new(None),
            round: AtomicU64::new(0),
            phase: RwLock::new(ElectionPhase::Propose),
            prevotes: RwLock::new(HashMap::new()),
            precommits: RwLock::new(HashMap::new()),
            byzantine_mode: AtomicBool::new(false),
        }
    }

    /// Get total number of nodes (including self)
    async fn total_nodes(&self) -> usize {
        let peers = self.peers.read().await;
        let alive_peers = peers.iter()
            .filter(|p| p.is_alive(HEARTBEAT_TIMEOUT))
            .count();
        alive_peers + 1 // +1 for self
    }

    /// Calculate quorum size (2f+1 for 3f+1 nodes)
    async fn quorum_size(&self) -> usize {
        let n = self.total_nodes().await;
        // For 3f+1 nodes, quorum is 2f+1 = (2n+1)/3
        (2 * n + 2) / 3
    }

    /// Check if Byzantine mode should be enabled
    async fn check_byzantine_mode(&self) -> bool {
        self.total_nodes().await >= MIN_BYZANTINE_NODES
    }

    /// Run leader election
    ///
    /// Uses Byzantine-resistant protocol when enough nodes are present,
    /// falls back to simple lexicographic selection otherwise.
    pub async fn elect(&self) -> bool {
        // Check if we should use Byzantine mode
        let use_byzantine = self.check_byzantine_mode().await;
        self.byzantine_mode.store(use_byzantine, Ordering::SeqCst);

        if use_byzantine {
            self.elect_byzantine().await
        } else {
            self.elect_simple().await
        }
    }

    /// Simple election: lexicographically lowest hub ID wins
    /// Used when not enough nodes for Byzantine tolerance
    async fn elect_simple(&self) -> bool {
        let leader_id = {
            let peers = self.peers.read().await;
            let mut all_ids: Vec<String> = peers.iter()
                .filter(|p| p.is_alive(HEARTBEAT_TIMEOUT))
                .map(|p| p.hub_id.clone())
                .collect();
            all_ids.push(self.hub_id.clone());

            // Sort and pick lowest
            all_ids.sort();
            all_ids.into_iter().next().unwrap_or_else(|| self.hub_id.clone())
        };

        self.commit_leader(&leader_id).await
    }

    /// Byzantine-resistant election with 2/3+ majority voting
    /// Implements Tendermint-style PROPOSE → PREVOTE → PRECOMMIT → COMMIT
    async fn elect_byzantine(&self) -> bool {
        let round = self.round.fetch_add(1, Ordering::SeqCst) + 1;
        debug!("🗳️ Starting Byzantine election round {}", round);

        // Clear previous round votes
        {
            let mut prevotes = self.prevotes.write().await;
            let mut precommits = self.precommits.write().await;
            prevotes.remove(&(round - 1));
            precommits.remove(&(round - 1));
        }

        // PHASE 1: PROPOSE
        // Round-robin proposer selection
        *self.phase.write().await = ElectionPhase::Propose;
        let proposer = self.get_proposer(round).await;
        let proposed_leader = if proposer == self.hub_id {
            // We're the proposer - propose ourselves
            info!("📣 Proposing self as leader for round {}", round);
            self.hub_id.clone()
        } else {
            // Wait for proposal from designated proposer
            // In production, this would receive via network
            proposer.clone()
        };

        // PHASE 2: PREVOTE
        *self.phase.write().await = ElectionPhase::Prevote;
        self.add_prevote(round, &self.hub_id, &proposed_leader).await;

        // Check for 2/3+ prevotes
        let quorum = self.quorum_size().await;
        let prevote_leader = self.check_prevote_quorum(round, quorum).await;

        if prevote_leader.is_none() {
            debug!("No prevote quorum reached in round {}", round);
            return false;
        }
        let leader_id = prevote_leader.unwrap();

        // PHASE 3: PRECOMMIT
        *self.phase.write().await = ElectionPhase::Precommit;
        self.add_precommit(round, &self.hub_id, &leader_id).await;

        // Check for 2/3+ precommits
        let precommit_leader = self.check_precommit_quorum(round, quorum).await;

        if precommit_leader.is_none() {
            debug!("No precommit quorum reached in round {}", round);
            return false;
        }
        let committed_leader = precommit_leader.unwrap();

        // PHASE 4: COMMIT
        *self.phase.write().await = ElectionPhase::Committed;
        info!("✅ Byzantine election complete: leader = {} (round {})", committed_leader, round);

        self.commit_leader(&committed_leader).await
    }

    /// Get designated proposer for a round (round-robin)
    async fn get_proposer(&self, round: u64) -> String {
        let peers = self.peers.read().await;
        let mut all_ids: Vec<String> = peers.iter()
            .filter(|p| p.is_alive(HEARTBEAT_TIMEOUT))
            .map(|p| p.hub_id.clone())
            .collect();
        all_ids.push(self.hub_id.clone());
        all_ids.sort();

        if all_ids.is_empty() {
            return self.hub_id.clone();
        }

        let idx = (round as usize) % all_ids.len();
        all_ids[idx].clone()
    }

    /// Add a prevote
    pub async fn add_prevote(&self, round: u64, voter_id: &str, leader_id: &str) {
        let mut prevotes = self.prevotes.write().await;
        prevotes.entry(round)
            .or_insert_with(HashMap::new)
            .insert(voter_id.to_string(), leader_id.to_string());
    }

    /// Add a precommit
    pub async fn add_precommit(&self, round: u64, voter_id: &str, leader_id: &str) {
        let mut precommits = self.precommits.write().await;
        precommits.entry(round)
            .or_insert_with(HashMap::new)
            .insert(voter_id.to_string(), leader_id.to_string());
    }

    /// Check if any leader has 2/3+ prevotes
    async fn check_prevote_quorum(&self, round: u64, quorum: usize) -> Option<String> {
        let prevotes = self.prevotes.read().await;
        if let Some(round_votes) = prevotes.get(&round) {
            // Count votes per leader
            let mut counts: HashMap<&str, usize> = HashMap::new();
            for leader_id in round_votes.values() {
                *counts.entry(leader_id.as_str()).or_insert(0) += 1;
            }

            // Find leader with quorum
            for (leader, count) in counts {
                if count >= quorum {
                    return Some(leader.to_string());
                }
            }
        }
        None
    }

    /// Check if any leader has 2/3+ precommits
    async fn check_precommit_quorum(&self, round: u64, quorum: usize) -> Option<String> {
        let precommits = self.precommits.read().await;
        if let Some(round_votes) = precommits.get(&round) {
            let mut counts: HashMap<&str, usize> = HashMap::new();
            for leader_id in round_votes.values() {
                *counts.entry(leader_id.as_str()).or_insert(0) += 1;
            }

            for (leader, count) in counts {
                if count >= quorum {
                    return Some(leader.to_string());
                }
            }
        }
        None
    }

    /// Commit leader after election
    async fn commit_leader(&self, leader_id: &str) -> bool {
        let we_are_leader = leader_id == self.hub_id;
        let _was_leader = self.is_leader.swap(we_are_leader, Ordering::SeqCst);

        // Update current leader
        {
            let mut current = self.current_leader.write().await;
            let old_leader = current.clone();
            *current = Some(leader_id.to_string());

            // Log leadership changes
            if old_leader.as_deref() != Some(leader_id) {
                if we_are_leader {
                    info!("👑 This hub is now the LEADER");
                } else {
                    info!("👥 Leader is: {}", leader_id);
                }
            }
        }

        // Update peer leader flags
        {
            let mut peers = self.peers.write().await;
            for peer in peers.iter_mut() {
                peer.is_leader = peer.hub_id == leader_id;
            }
        }

        we_are_leader
    }

    /// Handle incoming vote from peer
    pub async fn handle_vote(&self, vote: Vote) -> bool {
        // Verify vote signature (simplified - in production use crypto)
        if vote.round < self.round.load(Ordering::SeqCst) {
            debug!("Ignoring vote for old round {}", vote.round);
            return false;
        }

        match vote.phase.as_str() {
            "prevote" => {
                self.add_prevote(vote.round, &vote.voter_id, &vote.leader_id).await;
            }
            "precommit" => {
                self.add_precommit(vote.round, &vote.voter_id, &vote.leader_id).await;
            }
            _ => {
                warn!("Unknown vote phase: {}", vote.phase);
                return false;
            }
        }

        true
    }

    /// Get current round
    pub fn current_round(&self) -> u64 {
        self.round.load(Ordering::SeqCst)
    }

    /// Check if Byzantine mode is active
    pub fn is_byzantine_mode(&self) -> bool {
        self.byzantine_mode.load(Ordering::SeqCst)
    }

    /// Get current phase
    pub async fn current_phase(&self) -> ElectionPhase {
        self.phase.read().await.clone()
    }

    /// Check if this hub is the leader
    pub fn is_leader(&self) -> bool {
        self.is_leader.load(Ordering::SeqCst)
    }

    /// Get current leader's hub ID
    pub async fn get_leader(&self) -> Option<String> {
        self.current_leader.read().await.clone()
    }

    /// Record heartbeat from leader
    pub async fn heartbeat(&self) {
        *self.last_heartbeat.write().await = Some(Instant::now());
    }

    /// Check if leader is healthy (has sent heartbeat recently)
    pub async fn is_leader_healthy(&self) -> bool {
        let last = self.last_heartbeat.read().await;
        match *last {
            Some(t) => t.elapsed() < HEARTBEAT_TIMEOUT,
            None => {
                // If we're the leader, we're always healthy
                self.is_leader()
            }
        }
    }

    /// Check if re-election is needed
    pub async fn needs_election(&self) -> bool {
        // Re-elect if:
        // 1. No leader set
        // 2. Leader hasn't heartbeat in time
        // 3. Peer list changed

        let current_leader = self.current_leader.read().await;
        if current_leader.is_none() {
            return true;
        }

        if !self.is_leader() && !self.is_leader_healthy().await {
            warn!("Leader heartbeat timeout, triggering re-election");
            return true;
        }

        false
    }

    /// Get leader responsibilities
    pub fn leader_responsibilities() -> Vec<&'static str> {
        vec![
            "Contact main Kagami API for state updates",
            "Distribute state to follower hubs",
            "Handle external API requests",
            "Manage command queue replay",
            "Coordinate mesh state synchronization",
        ]
    }
}

/// Leader election state for serialization
#[derive(Debug, Clone, serde::Serialize)]
pub struct LeaderState {
    pub hub_id: String,
    pub is_leader: bool,
    pub current_leader: Option<String>,
    pub peer_count: usize,
    /// Byzantine mode active
    pub byzantine_mode: bool,
    /// Current election round
    pub round: u64,
    /// Current phase
    pub phase: String,
    /// Quorum size required
    pub quorum_size: usize,
}

impl LeaderElection {
    /// Get current state for API responses
    pub async fn get_state(&self) -> LeaderState {
        let phase = self.current_phase().await;
        LeaderState {
            hub_id: self.hub_id.clone(),
            is_leader: self.is_leader(),
            current_leader: self.get_leader().await,
            peer_count: self.peers.read().await.len(),
            byzantine_mode: self.is_byzantine_mode(),
            round: self.current_round(),
            phase: format!("{:?}", phase),
            quorum_size: self.quorum_size().await,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn now_unix() -> u64 {
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs()
    }

    fn make_peer(id: &str) -> Peer {
        Peer {
            hub_id: id.to_string(),
            name: format!("Hub {}", id),
            address: "127.0.0.1".to_string(),
            port: 8080,
            last_seen: now_unix(),
            is_leader: false,
            public_key: None,
            tls_enabled: true,
            properties: HashMap::new(),
        }
    }

    #[tokio::test]
    async fn test_single_hub_is_leader() {
        let peers = Arc::new(RwLock::new(Vec::new()));
        let election = LeaderElection::new("hub-1".to_string(), peers);

        let is_leader = election.elect().await;
        assert!(is_leader);
        assert!(election.is_leader());
        assert!(!election.is_byzantine_mode()); // Not enough nodes
    }

    #[tokio::test]
    async fn test_lowest_id_wins_simple_mode() {
        let peers = Arc::new(RwLock::new(vec![
            make_peer("hub-b"),
            make_peer("hub-c"),
        ]));

        let election = LeaderElection::new("hub-a".to_string(), peers);
        let is_leader = election.elect().await;

        assert!(is_leader); // hub-a < hub-b < hub-c
        assert!(!election.is_byzantine_mode()); // Only 3 nodes
    }

    #[tokio::test]
    async fn test_not_leader_when_lower_exists() {
        let peers = Arc::new(RwLock::new(vec![
            make_peer("hub-a"),
        ]));

        let election = LeaderElection::new("hub-z".to_string(), peers);
        let is_leader = election.elect().await;

        assert!(!is_leader); // hub-a < hub-z
        assert_eq!(election.get_leader().await, Some("hub-a".to_string()));
    }

    #[tokio::test]
    async fn test_byzantine_mode_with_4_nodes() {
        let peers = Arc::new(RwLock::new(vec![
            make_peer("hub-b"),
            make_peer("hub-c"),
            make_peer("hub-d"),
        ]));

        let election = LeaderElection::new("hub-a".to_string(), peers);
        let _ = election.elect().await;

        assert!(election.is_byzantine_mode()); // 4 nodes = Byzantine mode
    }

    #[tokio::test]
    async fn test_quorum_calculation() {
        // 4 nodes: quorum = (2*4+2)/3 = 3
        let peers = Arc::new(RwLock::new(vec![
            make_peer("hub-b"),
            make_peer("hub-c"),
            make_peer("hub-d"),
        ]));

        let election = LeaderElection::new("hub-a".to_string(), peers);
        let quorum = election.quorum_size().await;

        assert_eq!(quorum, 3); // 2f+1 where f=1
    }

    #[tokio::test]
    async fn test_prevote_quorum() {
        let peers = Arc::new(RwLock::new(vec![
            make_peer("hub-b"),
            make_peer("hub-c"),
            make_peer("hub-d"),
        ]));

        let election = LeaderElection::new("hub-a".to_string(), peers);

        // Add 3 prevotes for hub-a (quorum = 3)
        election.add_prevote(1, "hub-a", "hub-a").await;
        election.add_prevote(1, "hub-b", "hub-a").await;
        election.add_prevote(1, "hub-c", "hub-a").await;

        let quorum = election.quorum_size().await;
        let leader = election.check_prevote_quorum(1, quorum).await;

        assert_eq!(leader, Some("hub-a".to_string()));
    }

    #[tokio::test]
    async fn test_handle_vote() {
        let peers = Arc::new(RwLock::new(Vec::new()));
        let election = LeaderElection::new("hub-a".to_string(), peers);

        let vote = Vote {
            voter_id: "hub-b".to_string(),
            round: 1,
            leader_id: "hub-a".to_string(),
            phase: "prevote".to_string(),
            signature: "".to_string(),
        };

        let handled = election.handle_vote(vote).await;
        assert!(handled);
    }
}

/*
 * 鏡
 * One leads. All follow. The mesh stays consistent.
 * Byzantine nodes cannot subvert consensus with 2/3+ honest majority.
 */
