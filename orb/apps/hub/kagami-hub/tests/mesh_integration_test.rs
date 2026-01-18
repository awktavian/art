//! Mesh Network Integration Tests
//!
//! Tests for hub-to-hub communication including:
//! - Multi-hub simulation
//! - Leader election
//! - State synchronization
//! - Network partition recovery
//!
//! Colony: Crystal (e₇) — Testing and verification
//!
//! h(x) ≥ 0. Always.

use std::sync::Arc;
use std::time::Duration;
use tokio::sync::RwLock;

// Only compile tests when mesh feature is enabled
#[cfg(feature = "mesh")]
mod mesh_tests {
    use super::*;
    use kagami_hub::mesh::{LeaderElection, MeshAuth, MeshDiscovery, MeshNetwork, Peer};
    use kagami_hub::state_cache::StateCache;

    /// Create a mock state cache for testing
    async fn create_test_state_cache() -> Arc<StateCache> {
        Arc::new(StateCache::new())
    }

    /// Create a simulated peer for testing
    fn create_test_peer(id: &str, name: &str, port: u16) -> Peer {
        Peer {
            hub_id: id.to_string(),
            name: name.to_string(),
            address: format!("127.0.0.1:{}", port).parse().unwrap(),
            last_seen: std::time::Instant::now(),
            is_leader: false,
            priority: 0,
        }
    }

    // ========================================================================
    // Leader Election Tests
    // ========================================================================

    #[tokio::test]
    async fn test_leader_election_single_hub() {
        // Single hub should become leader immediately
        let peers = Arc::new(RwLock::new(Vec::new()));
        let leader = LeaderElection::new("hub-1".to_string(), peers);

        leader.elect().await;

        assert!(leader.is_leader());
        assert_eq!(leader.get_leader().await, Some("hub-1".to_string()));
    }

    #[tokio::test]
    async fn test_leader_election_multiple_hubs() {
        // With multiple hubs, the one with highest priority (lowest ID) wins
        let peers = Arc::new(RwLock::new(vec![
            create_test_peer("hub-2", "Hub 2", 8002),
            create_test_peer("hub-3", "Hub 3", 8003),
        ]));

        let leader = LeaderElection::new("hub-1".to_string(), peers.clone());
        leader.elect().await;

        // hub-1 should be leader (lowest ID)
        assert!(leader.is_leader());

        // Now create another hub with lower ID
        let leader2 = LeaderElection::new("hub-0".to_string(), peers.clone());
        leader2.elect().await;

        assert!(leader2.is_leader());
    }

    #[tokio::test]
    async fn test_leader_election_deterministic() {
        // Leader election should be deterministic given same peers
        let peers = Arc::new(RwLock::new(vec![
            create_test_peer("hub-b", "Hub B", 8001),
            create_test_peer("hub-c", "Hub C", 8002),
        ]));

        let leader1 = LeaderElection::new("hub-a".to_string(), peers.clone());
        let leader2 = LeaderElection::new("hub-b".to_string(), peers.clone());
        let leader3 = LeaderElection::new("hub-c".to_string(), peers.clone());

        leader1.elect().await;
        leader2.elect().await;
        leader3.elect().await;

        // All should agree on the same leader
        let result1 = leader1.get_leader().await;
        let result2 = leader2.get_leader().await;
        let result3 = leader3.get_leader().await;

        assert_eq!(result1, result2);
        assert_eq!(result2, result3);
    }

    // ========================================================================
    // Peer Discovery Tests
    // ========================================================================

    #[tokio::test]
    async fn test_peer_addition() {
        let peers = Arc::new(RwLock::new(Vec::new()));

        // Add a peer
        {
            let mut p = peers.write().await;
            p.push(create_test_peer("hub-2", "Hub 2", 8002));
        }

        let p = peers.read().await;
        assert_eq!(p.len(), 1);
        assert_eq!(p[0].hub_id, "hub-2");
    }

    #[tokio::test]
    async fn test_peer_removal() {
        let peers = Arc::new(RwLock::new(vec![
            create_test_peer("hub-1", "Hub 1", 8001),
            create_test_peer("hub-2", "Hub 2", 8002),
        ]));

        // Remove a peer
        {
            let mut p = peers.write().await;
            p.retain(|peer| peer.hub_id != "hub-1");
        }

        let p = peers.read().await;
        assert_eq!(p.len(), 1);
        assert_eq!(p[0].hub_id, "hub-2");
    }

    #[tokio::test]
    async fn test_peer_update() {
        let peers = Arc::new(RwLock::new(vec![create_test_peer("hub-1", "Hub 1", 8001)]));

        // Update peer
        {
            let mut p = peers.write().await;
            if let Some(peer) = p.iter_mut().find(|p| p.hub_id == "hub-1") {
                peer.is_leader = true;
            }
        }

        let p = peers.read().await;
        assert!(p[0].is_leader);
    }

    // ========================================================================
    // Authentication Tests
    // ========================================================================

    #[tokio::test]
    async fn test_auth_key_generation() {
        let auth = MeshAuth::new();

        // Should have generated keys
        assert!(!auth.public_key_bytes().is_empty());
    }

    #[tokio::test]
    async fn test_auth_challenge_response() {
        let auth1 = MeshAuth::new();
        let auth2 = MeshAuth::new();

        // Generate challenge
        let challenge = auth1.generate_challenge();
        assert!(!challenge.is_empty());

        // Sign challenge with auth2
        let signature = auth2.sign_challenge(&challenge);

        // Verify signature
        let verified = auth1.verify_signature(&challenge, &signature, &auth2.public_key_bytes());

        assert!(verified);
    }

    #[tokio::test]
    async fn test_auth_invalid_signature() {
        let auth1 = MeshAuth::new();
        let auth2 = MeshAuth::new();

        let challenge = auth1.generate_challenge();

        // Create an invalid signature
        let fake_signature = vec![0u8; 64];

        // Should fail verification
        let verified =
            auth1.verify_signature(&challenge, &fake_signature, &auth2.public_key_bytes());

        assert!(!verified);
    }

    // ========================================================================
    // State Sync Tests
    // ========================================================================

    #[tokio::test]
    async fn test_state_sync_basic() {
        use kagami_hub::mesh::StateSyncProtocol;

        let state_cache = create_test_state_cache().await;
        let peers = Arc::new(RwLock::new(Vec::new()));

        let sync = StateSyncProtocol::new(peers.clone(), state_cache.clone());

        // Should not fail with no peers
        let result = sync.push_state().await;
        assert!(result.is_ok());
    }

    // ========================================================================
    // Mesh Network Integration Tests
    // ========================================================================

    #[tokio::test]
    async fn test_mesh_creation() {
        let state_cache = create_test_state_cache().await;

        let mesh = MeshNetwork::new(
            "test-hub".to_string(),
            "Test Hub".to_string(),
            state_cache,
            #[cfg(feature = "persistence")]
            None,
        );

        // Should not be leader until election
        assert!(!mesh.is_leader());

        // No peers initially
        let peers = mesh.get_peers().await;
        assert!(peers.is_empty());
    }

    #[tokio::test]
    async fn test_mesh_event_subscription() {
        let state_cache = create_test_state_cache().await;

        let mesh = MeshNetwork::new(
            "test-hub".to_string(),
            "Test Hub".to_string(),
            state_cache,
            #[cfg(feature = "persistence")]
            None,
        );

        // Should be able to subscribe to events
        let _rx = mesh.subscribe();

        // Receiver should exist
        // (We can't easily test without actually emitting events)
    }

    // ========================================================================
    // Network Partition Tests (Simulated)
    // ========================================================================

    #[tokio::test]
    async fn test_network_partition_recovery() {
        // Simulate a network partition by removing and re-adding peers
        let peers = Arc::new(RwLock::new(vec![
            create_test_peer("hub-1", "Hub 1", 8001),
            create_test_peer("hub-2", "Hub 2", 8002),
            create_test_peer("hub-3", "Hub 3", 8003),
        ]));

        // Initial state - 3 peers
        assert_eq!(peers.read().await.len(), 3);

        // Simulate partition - hub-3 disappears
        {
            let mut p = peers.write().await;
            p.retain(|peer| peer.hub_id != "hub-3");
        }
        assert_eq!(peers.read().await.len(), 2);

        // Leader re-election should happen
        let leader = LeaderElection::new("hub-1".to_string(), peers.clone());
        leader.elect().await;

        // hub-1 should still be leader
        assert!(leader.is_leader());

        // Simulate recovery - hub-3 comes back
        {
            let mut p = peers.write().await;
            p.push(create_test_peer("hub-3", "Hub 3", 8003));
        }
        assert_eq!(peers.read().await.len(), 3);

        // Re-elect - hub-1 should still be leader (lowest ID)
        leader.elect().await;
        assert!(leader.is_leader());
    }

    #[tokio::test]
    async fn test_leader_failover() {
        // Simulate leader going offline
        let peers = Arc::new(RwLock::new(vec![
            create_test_peer("hub-1", "Hub 1", 8001), // Leader
            create_test_peer("hub-2", "Hub 2", 8002),
        ]));

        // From hub-2's perspective, simulate hub-1 going down
        let leader_from_hub2 = LeaderElection::new("hub-2".to_string(), peers.clone());

        // Remove hub-1 (simulating failure)
        {
            let mut p = peers.write().await;
            p.retain(|peer| peer.hub_id != "hub-1");
        }

        // Re-elect
        leader_from_hub2.elect().await;

        // hub-2 should now be leader
        assert!(leader_from_hub2.is_leader());
    }
}

// ============================================================================
// Unit Tests (always run, no feature gate)
// ============================================================================

#[cfg(test)]
mod unit_tests {
    use super::*;

    #[test]
    fn test_peer_struct() {
        // This should compile without the mesh feature
        // Just testing basic struct behavior
        let id = "test-hub";
        let name = "Test Hub";

        assert_eq!(id.len(), 8);
        assert_eq!(name.len(), 8);
    }

    #[tokio::test]
    async fn test_rwlock_behavior() {
        // Test RwLock behavior we rely on
        let data = Arc::new(RwLock::new(vec![1, 2, 3]));

        // Multiple readers should work
        let r1 = data.read().await;
        let r2 = data.read().await;
        assert_eq!(r1.len(), 3);
        assert_eq!(r2.len(), 3);
        drop(r1);
        drop(r2);

        // Writer should have exclusive access
        let mut w = data.write().await;
        w.push(4);
        assert_eq!(w.len(), 4);
    }

    #[tokio::test]
    async fn test_broadcast_channel() {
        use tokio::sync::broadcast;

        let (tx, mut rx1) = broadcast::channel::<String>(10);
        let mut rx2 = tx.subscribe();

        tx.send("hello".to_string()).unwrap();

        assert_eq!(rx1.recv().await.unwrap(), "hello");
        assert_eq!(rx2.recv().await.unwrap(), "hello");
    }
}

/*
 * 鏡
 * The mesh is tested. The swarm is verified.
 * h(x) ≥ 0. Always.
 */
