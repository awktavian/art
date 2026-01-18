//! Mesh Networking — Hub-to-Hub Communication
//!
//! Enables multiple Kagami Hubs to:
//! - Discover each other via mDNS
//! - Elect a leader for API communication
//! - Synchronize state across the mesh
//! - Authenticate peer connections
//!
//! Colony: Nexus (e₄) — Connection and integration
//!
//! η → s → μ → a → η′
//! h(x) ≥ 0. Always.

pub mod auth;
pub mod bft_leader;
pub mod discovery;
pub mod leader;
#[cfg(feature = "persistence")]
pub mod ledger;
pub mod routing;
pub mod sync;

use std::sync::Arc;
use tokio::sync::{broadcast, RwLock};
use tracing::info;

use crate::state_cache::StateCache;

#[cfg(feature = "persistence")]
use crate::db::HubDatabase;

pub use discovery::{MeshDiscovery, Peer};
pub use leader::LeaderElection;
pub use bft_leader::{
    BftLeaderElection, BftConsensusState, BftMessage, Phase,
    Proposal, Vote, VoteType, ViewChangeRequest, ViewChangeReason,
    ConsensusEvent, LockedValue,
};
pub use routing::{CommandRouter, MeshCommand, CommandAck, CommandBuilder, RouteResult};
pub use sync::{StateSyncProtocol, CRDTState, VectorClock, VectorClockOrdering, ClockOrdering};
pub use auth::MeshAuth;
#[cfg(feature = "persistence")]
pub use ledger::{
    MeshLedger, ConsensusDecision, DecisionSignature, StateSnapshot,
    TransactionLogEntry, TransactionOperation, ByzantineEvidenceRecord,
    LedgerStats, RecoveryResult, PruneResult,
    SNAPSHOT_INTERVAL, PRUNE_AGE_DAYS,
};

/// Mesh network coordinator
pub struct MeshNetwork {
    /// This hub's unique ID
    hub_id: String,
    /// Hub name for display
    hub_name: String,

    /// Peer discovery
    discovery: Arc<MeshDiscovery>,
    /// Leader election (simple)
    leader: Arc<LeaderElection>,
    /// BFT leader election (Byzantine tolerant)
    bft_leader: Arc<BftLeaderElection>,
    /// State synchronization
    sync: Arc<StateSyncProtocol>,
    /// Authentication
    auth: Arc<MeshAuth>,
    /// Byzantine detector
    byzantine_detector: Arc<crate::byzantine::ByzantineDetector>,

    /// Known peers
    peers: Arc<RwLock<Vec<Peer>>>,
    /// State cache reference
    state_cache: Arc<StateCache>,

    /// Event channel
    event_tx: broadcast::Sender<MeshEvent>,
}

/// Events emitted by the mesh network
#[derive(Debug, Clone)]
pub enum MeshEvent {
    /// New peer discovered
    PeerDiscovered { peer: Peer },
    /// Peer went offline
    PeerLost { hub_id: String },
    /// Leader changed
    LeaderChanged { old: Option<String>, new: String },
    /// State received from leader
    StateReceived { from: String },
    /// Authentication succeeded
    AuthSuccess { peer: String },
    /// Authentication failed
    AuthFailed { peer: String, reason: String },
    /// Byzantine fault detected (Jan 4, 2026)
    ByzantineFaultDetected { peer: String, fault_type: String },
    /// Byzantine peer isolated
    ByzantinePeerIsolated { peer: String },
    /// BFT consensus reached
    BftConsensusReached { height: u64, leader: String },
}

impl MeshNetwork {
    /// Create a new mesh network
    pub fn new(
        hub_id: String,
        hub_name: String,
        state_cache: Arc<StateCache>,
        #[cfg(feature = "persistence")]
        _db: Option<Arc<HubDatabase>>,
    ) -> (Self, broadcast::Receiver<BftMessage>) {
        let (event_tx, _) = broadcast::channel(100);
        let peers = Arc::new(RwLock::new(Vec::new()));

        let auth = Arc::new(MeshAuth::new());
        let discovery = Arc::new(MeshDiscovery::new(
            hub_id.clone(),
            hub_name.clone(),
            peers.clone(),
        ));
        let leader = Arc::new(LeaderElection::new(
            hub_id.clone(),
            peers.clone(),
        ));

        // BFT leader election (Byzantine fault tolerant)
        let (bft_leader, bft_rx) = BftLeaderElection::new(
            hub_id.clone(),
            auth.clone(),
            peers.clone(),
        );
        let bft_leader = Arc::new(bft_leader);

        // Byzantine detector
        let byzantine_detector = Arc::new(crate::byzantine::ByzantineDetector::new(hub_id.clone()));

        let sync = Arc::new(StateSyncProtocol::new(
            peers.clone(),
            state_cache.clone(),
        ));

        (Self {
            hub_id,
            hub_name,
            discovery,
            leader,
            bft_leader,
            sync,
            auth,
            byzantine_detector,
            peers,
            state_cache,
            event_tx,
        }, bft_rx)
    }

    /// Start mesh networking
    pub async fn start(&self) -> anyhow::Result<()> {
        info!("🔗 Starting mesh network for hub: {}", self.hub_id);

        // Start mDNS discovery
        self.discovery.start().await?;

        // Initial leader election
        self.leader.elect().await;

        info!("Mesh network started");
        Ok(())
    }

    /// Subscribe to mesh events
    pub fn subscribe(&self) -> broadcast::Receiver<MeshEvent> {
        self.event_tx.subscribe()
    }

    /// Get current peers
    pub async fn get_peers(&self) -> Vec<Peer> {
        self.peers.read().await.clone()
    }

    /// Check if this hub is the leader
    pub fn is_leader(&self) -> bool {
        self.leader.is_leader()
    }

    /// Get leader hub ID
    pub async fn get_leader(&self) -> Option<String> {
        self.leader.get_leader().await
    }

    /// Broadcast state to all peers (if leader)
    pub async fn broadcast_state(&self) -> anyhow::Result<()> {
        if self.is_leader() {
            self.sync.push_state().await?;
        }
        Ok(())
    }

    /// Check if a peer is isolated due to Byzantine faults
    pub async fn is_peer_isolated(&self, peer_id: &str) -> bool {
        self.byzantine_detector.is_isolated(peer_id).await
    }

    /// Get BFT consensus state for API
    pub async fn get_bft_state(&self) -> BftConsensusState {
        self.bft_leader.get_state().await
    }

    /// Get Byzantine detector stats for API
    pub async fn get_byzantine_stats(&self) -> std::collections::HashMap<String, crate::byzantine::PeerFaultStats> {
        self.byzantine_detector.get_all_stats().await
    }

    /// Get list of isolated peers
    pub async fn get_isolated_peers(&self) -> Vec<String> {
        self.byzantine_detector.get_isolated_peers().await
    }

    /// Record a proposal and check for equivocation
    pub async fn record_proposal(
        &self,
        peer_id: &str,
        height: u64,
        round: u32,
        proposal_hash: Vec<u8>,
    ) -> bool {
        match self.byzantine_detector.record_proposal(peer_id, height, round, proposal_hash).await {
            Ok(_) => true,
            Err(evidence) => {
                // Emit Byzantine fault event
                let _ = self.event_tx.send(MeshEvent::ByzantineFaultDetected {
                    peer: peer_id.to_string(),
                    fault_type: format!("{:?}", evidence.fault_type),
                });
                false
            }
        }
    }

    /// Record a vote and check for equivocation
    pub async fn record_vote(
        &self,
        peer_id: &str,
        height: u64,
        round: u32,
        vote_type: &str,
        vote_hash: Vec<u8>,
    ) -> bool {
        match self.byzantine_detector.record_vote(peer_id, height, round, vote_type, vote_hash).await {
            Ok(_) => true,
            Err(evidence) => {
                // Emit Byzantine fault event
                let _ = self.event_tx.send(MeshEvent::ByzantineFaultDetected {
                    peer: peer_id.to_string(),
                    fault_type: format!("{:?}", evidence.fault_type),
                });
                false
            }
        }
    }
}

/*
 * 鏡
 * The mesh connects. The swarm remembers.
 */
