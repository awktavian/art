//! State Synchronization Protocol with CRDT Support
//!
//! Synchronizes state between hubs in the mesh using CRDTs
//! (Conflict-free Replicated Data Types) for eventual consistency.
//!
//! Features:
//! - Last-Writer-Wins Register for simple values
//! - G-Counter for incrementing metrics
//! - OR-Set for device/room collections
//! - Vector clocks for causality tracking (from kagami-mesh-sdk)
//! - Delta-state sync for bandwidth efficiency
//!
//! Colony: Nexus (e₄) — State distribution
//!
//! η → s → μ → a → η′
//! h(x) ≥ 0. Always.

use std::collections::{HashMap, HashSet};
use std::sync::Arc;
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use tokio::sync::RwLock;
use tracing::{debug, info, warn, error};
use serde::{Deserialize, Serialize};

use crate::state_cache::{StateCache, TeslaState, HomeState, WeatherState, ZoneLevel};
use super::Peer;

// Re-export VectorClock from kagami-mesh-sdk (canonical implementation)
pub use kagami_mesh_sdk::sync::{VectorClock, VectorClockOrdering};

/// Ordering relationship between vector clocks (compatibility alias)
/// Maps to kagami_mesh_sdk::sync::VectorClockOrdering
pub type ClockOrdering = VectorClockOrdering;

// ============================================================================
// Last-Writer-Wins Register (LWW-Register)
// ============================================================================
//
// NOTE: This is a Hub-specific implementation using u64 timestamps for
// compatibility with existing state types. For new code, prefer using
// kagami_mesh_sdk::sync::LwwRegister which uses chrono::DateTime<Utc> for
// better precision and timezone handling.
//
// Migration path: When domain types (ZoneLevel, TeslaState, etc.) are updated
// to implement Serialize + PartialOrd, switch to SDK types.
// ============================================================================

/// Last-Writer-Wins Register - simple CRDT for single values
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LWWRegister<T: Clone> {
    /// The value
    pub value: T,
    /// Timestamp when value was set (wall clock for LWW)
    pub timestamp: u64,
    /// Hub that set the value
    pub writer: String,
}

impl<T: Clone> LWWRegister<T> {
    /// Create a new LWW register
    pub fn new(value: T, writer: String) -> Self {
        Self {
            value,
            timestamp: current_timestamp(),
            writer,
        }
    }

    /// Update the value if this write is newer
    pub fn update(&mut self, value: T, timestamp: u64, writer: String) {
        // Last-Writer-Wins: higher timestamp wins
        // Tie-breaker: lexicographically higher writer ID
        if timestamp > self.timestamp ||
           (timestamp == self.timestamp && writer > self.writer) {
            self.value = value;
            self.timestamp = timestamp;
            self.writer = writer;
        }
    }

    /// Merge with another register
    pub fn merge(&mut self, other: &LWWRegister<T>) {
        self.update(other.value.clone(), other.timestamp, other.writer.clone());
    }
}

// ============================================================================
// G-Counter (Grow-only Counter)
// ============================================================================
//
// NOTE: For new code, prefer kagami_mesh_sdk::sync::GCounter which has an
// identical implementation but is maintained as the canonical source.
// ============================================================================

/// G-Counter CRDT - only increases, never decreases
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct GCounter {
    /// Per-hub counters
    counts: HashMap<String, u64>,
}

impl GCounter {
    /// Create a new G-Counter
    pub fn new() -> Self {
        Self::default()
    }

    /// Increment the counter for this hub
    pub fn increment(&mut self, hub_id: &str) {
        let count = self.counts.entry(hub_id.to_string()).or_insert(0);
        *count += 1;
    }

    /// Increment by a specific amount
    pub fn increment_by(&mut self, hub_id: &str, amount: u64) {
        let count = self.counts.entry(hub_id.to_string()).or_insert(0);
        *count += amount;
    }

    /// Get the total count across all hubs
    pub fn value(&self) -> u64 {
        self.counts.values().sum()
    }

    /// Merge with another G-Counter (take max of each hub's count)
    pub fn merge(&mut self, other: &GCounter) {
        for (hub_id, &count) in &other.counts {
            let current = self.counts.entry(hub_id.clone()).or_insert(0);
            *current = (*current).max(count);
        }
    }
}

// ============================================================================
// OR-Set (Observed-Remove Set)
// ============================================================================
//
// NOTE: For new code, prefer kagami_mesh_sdk::sync::OrSet which has an
// identical implementation but is maintained as the canonical source.
// The SDK version requires T: Serialize, which is needed for proper
// cross-platform synchronization.
// ============================================================================

/// Element in an OR-Set with unique tag
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, Hash)]
pub struct ORSetElement<T: Clone + Eq + std::hash::Hash> {
    pub value: T,
    /// Unique tag (hub_id + timestamp)
    pub tag: String,
}

/// OR-Set CRDT - supports add and remove with eventual consistency
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ORSet<T: Clone + Eq + std::hash::Hash> {
    /// Elements with their unique tags
    elements: HashSet<ORSetElement<T>>,
    /// Tombstones for removed elements
    tombstones: HashSet<String>,
}

impl<T: Clone + Eq + std::hash::Hash> Default for ORSet<T> {
    fn default() -> Self {
        Self::new()
    }
}

impl<T: Clone + Eq + std::hash::Hash> ORSet<T> {
    /// Create a new OR-Set
    pub fn new() -> Self {
        Self {
            elements: HashSet::new(),
            tombstones: HashSet::new(),
        }
    }

    /// Add an element
    pub fn add(&mut self, value: T, hub_id: &str) {
        let tag = format!("{}:{}", hub_id, current_timestamp());
        self.elements.insert(ORSetElement { value, tag });
    }

    /// Remove an element (marks all tags for this value as tombstones)
    pub fn remove(&mut self, value: &T) {
        let tags_to_remove: Vec<_> = self.elements.iter()
            .filter(|e| &e.value == value)
            .map(|e| e.tag.clone())
            .collect();

        for tag in tags_to_remove {
            self.tombstones.insert(tag.clone());
            self.elements.retain(|e| e.tag != tag);
        }
    }

    /// Check if an element is in the set
    pub fn contains(&self, value: &T) -> bool {
        self.elements.iter().any(|e| &e.value == value)
    }

    /// Get all current values
    pub fn values(&self) -> Vec<T> {
        self.elements.iter()
            .map(|e| e.value.clone())
            .collect::<HashSet<_>>()
            .into_iter()
            .collect()
    }

    /// Merge with another OR-Set
    pub fn merge(&mut self, other: &ORSet<T>) {
        // Add all tombstones
        self.tombstones.extend(other.tombstones.iter().cloned());

        // Add elements that aren't tombstoned
        for element in &other.elements {
            if !self.tombstones.contains(&element.tag) {
                self.elements.insert(element.clone());
            }
        }

        // Remove tombstoned elements from our set
        self.elements.retain(|e| !self.tombstones.contains(&e.tag));
    }
}

// ============================================================================
// CRDT State
// ============================================================================

/// Full CRDT-backed state for synchronization
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CRDTState {
    /// Vector clock for causality
    pub clock: VectorClock,
    /// Zone level (LWW)
    pub zone: LWWRegister<ZoneLevel>,
    /// Tesla state (LWW)
    pub tesla: Option<LWWRegister<TeslaState>>,
    /// Home state (LWW)
    pub home: Option<LWWRegister<HomeState>>,
    /// Weather state (LWW)
    pub weather: Option<LWWRegister<WeatherState>>,
    /// Active rooms (OR-Set)
    pub active_rooms: ORSet<String>,
    /// Sync counter
    pub sync_count: GCounter,
    /// Source hub ID
    pub source_hub: String,
    /// Timestamp
    pub timestamp: u64,
}

impl CRDTState {
    /// Create a new CRDT state
    pub fn new(hub_id: String) -> Self {
        Self {
            clock: VectorClock::new(),
            zone: LWWRegister::new(ZoneLevel::UnthinkingDepths, hub_id.clone()),
            tesla: None,
            home: None,
            weather: None,
            active_rooms: ORSet::new(),
            sync_count: GCounter::new(),
            source_hub: hub_id,
            timestamp: current_timestamp(),
        }
    }

    /// Merge with another CRDT state
    pub fn merge(&mut self, other: &CRDTState) {
        // Merge vector clock
        self.clock.merge(&other.clock);

        // Merge LWW registers
        self.zone.merge(&other.zone);

        if let Some(ref other_tesla) = other.tesla {
            match &mut self.tesla {
                Some(tesla) => tesla.merge(other_tesla),
                None => self.tesla = Some(other_tesla.clone()),
            }
        }

        if let Some(ref other_home) = other.home {
            match &mut self.home {
                Some(home) => home.merge(other_home),
                None => self.home = Some(other_home.clone()),
            }
        }

        if let Some(ref other_weather) = other.weather {
            match &mut self.weather {
                Some(weather) => weather.merge(other_weather),
                None => self.weather = Some(other_weather.clone()),
            }
        }

        // Merge OR-Set
        self.active_rooms.merge(&other.active_rooms);

        // Merge counters
        self.sync_count.merge(&other.sync_count);

        // Update timestamp
        self.timestamp = current_timestamp();
    }
}

// ============================================================================
// Full State (Legacy Compatibility)
// ============================================================================

/// Full state snapshot for synchronization (legacy format)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FullState {
    /// Zone level
    pub zone: ZoneLevel,
    /// Tesla state (if available)
    pub tesla: Option<TeslaState>,
    /// Home state (if available)
    pub home: Option<HomeState>,
    /// Weather state (if available)
    pub weather: Option<WeatherState>,
    /// Timestamp when snapshot was taken
    pub timestamp: u64,
    /// Source hub ID
    pub source_hub: String,
}

impl FullState {
    /// Convert to CRDT state
    pub fn to_crdt(&self) -> CRDTState {
        let mut state = CRDTState::new(self.source_hub.clone());
        state.zone = LWWRegister::new(self.zone.clone(), self.source_hub.clone());
        state.tesla = self.tesla.clone().map(|t| LWWRegister::new(t, self.source_hub.clone()));
        state.home = self.home.clone().map(|h| LWWRegister::new(h, self.source_hub.clone()));
        state.weather = self.weather.clone().map(|w| LWWRegister::new(w, self.source_hub.clone()));
        state.timestamp = self.timestamp;
        state
    }

    /// Convert from CRDT state
    pub fn from_crdt(crdt: &CRDTState) -> Self {
        Self {
            zone: crdt.zone.value.clone(),
            tesla: crdt.tesla.as_ref().map(|r| r.value.clone()),
            home: crdt.home.as_ref().map(|r| r.value.clone()),
            weather: crdt.weather.as_ref().map(|r| r.value.clone()),
            timestamp: crdt.timestamp,
            source_hub: crdt.source_hub.clone(),
        }
    }
}

// ============================================================================
// State Synchronization Protocol
// ============================================================================

/// State synchronization protocol with CRDT support
pub struct StateSyncProtocol {
    /// This hub's ID
    hub_id: String,
    /// Known peers
    peers: Arc<RwLock<Vec<Peer>>>,
    /// State cache
    state_cache: Arc<StateCache>,
    /// CRDT state
    crdt_state: Arc<RwLock<CRDTState>>,
    /// HTTP client for syncing
    client: reqwest::Client,
    /// Sync status
    status: Arc<RwLock<SyncStatus>>,
}

impl StateSyncProtocol {
    /// Create a new state sync protocol
    pub fn new(
        peers: Arc<RwLock<Vec<Peer>>>,
        state_cache: Arc<StateCache>,
    ) -> Self {
        Self::with_hub_id("local".to_string(), peers, state_cache)
    }

    /// Create with specific hub ID
    pub fn with_hub_id(
        hub_id: String,
        peers: Arc<RwLock<Vec<Peer>>>,
        state_cache: Arc<StateCache>,
    ) -> Self {
        Self {
            crdt_state: Arc::new(RwLock::new(CRDTState::new(hub_id.clone()))),
            hub_id,
            peers,
            state_cache,
            client: reqwest::Client::builder()
                .timeout(Duration::from_secs(10))
                .build()
                .expect("Failed to create HTTP client"),
            status: Arc::new(RwLock::new(SyncStatus::default())),
        }
    }

    /// Push state to all followers (leader only)
    pub async fn push_state(&self) -> anyhow::Result<()> {
        let state = self.get_crdt_state().await;
        let peers = self.peers.read().await;

        let follower_count = peers.iter().filter(|p| !p.is_leader).count();
        if follower_count == 0 {
            debug!("No followers to push state to");
            return Ok(());
        }

        info!("Pushing CRDT state to {} followers", follower_count);

        let mut success_count = 0;
        let mut error_count = 0;

        for peer in peers.iter().filter(|p| !p.is_leader) {
            match self.push_to_peer(peer, &state).await {
                Ok(_) => success_count += 1,
                Err(e) => {
                    warn!("Failed to push state to {}: {}", peer.name, e);
                    error_count += 1;
                }
            }
        }

        // Update status
        {
            let mut status = self.status.write().await;
            status.last_sync = Some(current_timestamp());
            status.sync_count += success_count;
            status.error_count += error_count;
        }

        // Increment sync counter
        {
            let mut crdt = self.crdt_state.write().await;
            crdt.sync_count.increment(&self.hub_id);
            crdt.clock.increment(&self.hub_id);
        }

        Ok(())
    }

    /// Push CRDT state to a specific peer
    async fn push_to_peer(&self, peer: &Peer, state: &CRDTState) -> anyhow::Result<()> {
        let url = format!("{}/api/mesh/crdt-state", peer.api_url());

        self.client
            .post(&url)
            .json(state)
            .send()
            .await?
            .error_for_status()?;

        debug!("Pushed CRDT state to {}", peer.name);
        Ok(())
    }

    /// Request state from leader (follower only)
    pub async fn request_state(&self) -> anyhow::Result<CRDTState> {
        let peers = self.peers.read().await;

        let leader = peers.iter()
            .find(|p| p.is_leader)
            .ok_or_else(|| anyhow::anyhow!("No leader found"))?;

        let url = format!("{}/api/mesh/crdt-state", leader.api_url());

        let state: CRDTState = self.client
            .get(&url)
            .send()
            .await?
            .error_for_status()?
            .json()
            .await?;

        info!("Received CRDT state from leader {}", leader.name);

        // Merge received state
        self.merge_state(state.clone()).await;

        Ok(state)
    }

    /// Merge received CRDT state
    pub async fn merge_state(&self, other: CRDTState) {
        let mut crdt = self.crdt_state.write().await;
        crdt.merge(&other);

        info!(
            "Merged state from {} (clock: {:?})",
            other.source_hub,
            crdt.clock
        );

        // Update status
        let mut status = self.status.write().await;
        status.last_sync = Some(current_timestamp());
        status.sync_count += 1;
        status.lag_seconds = Some(current_timestamp().saturating_sub(other.timestamp));
    }

    /// Get current CRDT state
    pub async fn get_crdt_state(&self) -> CRDTState {
        let mut crdt = self.crdt_state.write().await;

        // Update from state cache
        crdt.zone = LWWRegister::new(
            self.state_cache.get_zone().await,
            self.hub_id.clone(),
        );

        if let Some(tesla) = self.state_cache.get_tesla().await {
            crdt.tesla = Some(LWWRegister::new(tesla, self.hub_id.clone()));
        }

        if let Some(home) = self.state_cache.get_home().await {
            crdt.home = Some(LWWRegister::new(home, self.hub_id.clone()));
        }

        if let Some(weather) = self.state_cache.get_weather().await {
            crdt.weather = Some(LWWRegister::new(weather, self.hub_id.clone()));
        }

        crdt.source_hub = self.hub_id.clone();
        crdt.timestamp = current_timestamp();
        crdt.clock.increment(&self.hub_id);

        crdt.clone()
    }

    /// Get full state (legacy format)
    pub async fn get_full_state(&self) -> FullState {
        let crdt = self.get_crdt_state().await;
        FullState::from_crdt(&crdt)
    }

    /// Apply received state from leader (legacy)
    pub async fn apply_state(&self, state: FullState) -> anyhow::Result<()> {
        let crdt = state.to_crdt();
        self.merge_state(crdt).await;
        Ok(())
    }

    /// Get sync status
    pub async fn get_status(&self) -> SyncStatus {
        self.status.read().await.clone()
    }

    /// Calculate delta since a given vector clock
    pub async fn calculate_delta(&self, since: &VectorClock) -> Option<CRDTState> {
        let crdt = self.crdt_state.read().await;

        // If their clock is not before ours, no delta needed
        if since.compare(&crdt.clock) != VectorClockOrdering::HappensBefore {
            return None;
        }

        // Return our full state as the delta
        // (In a more sophisticated implementation, we'd track and return only changed fields)
        Some(crdt.clone())
    }
}

// ============================================================================
// State Differences
// ============================================================================

/// State differences for efficient sync
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StateDiff {
    pub tesla_changed: bool,
    pub home_changed: bool,
    pub weather_changed: bool,
    pub zone_changed: bool,
}

impl StateDiff {
    /// Check if any state changed
    pub fn has_changes(&self) -> bool {
        self.tesla_changed || self.home_changed || self.weather_changed || self.zone_changed
    }
}

// ============================================================================
// Sync Status
// ============================================================================

/// Sync status for monitoring
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct SyncStatus {
    /// Last successful sync timestamp
    pub last_sync: Option<u64>,
    /// Number of successful syncs
    pub sync_count: u64,
    /// Number of failed syncs
    pub error_count: u64,
    /// Current sync lag (seconds behind leader)
    pub lag_seconds: Option<u64>,
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

// ============================================================================
// Tests
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_vector_clock_increment() {
        let mut clock = VectorClock::new();

        clock.increment("hub-1");
        assert_eq!(clock.get("hub-1"), 1);

        clock.increment("hub-1");
        assert_eq!(clock.get("hub-1"), 2);

        assert_eq!(clock.get("hub-2"), 0);
    }

    #[test]
    fn test_vector_clock_merge() {
        let mut clock1 = VectorClock::new();
        clock1.increment("hub-1");
        clock1.increment("hub-1");

        let mut clock2 = VectorClock::new();
        clock2.increment("hub-2");

        clock1.merge(&clock2);

        assert_eq!(clock1.get("hub-1"), 2);
        assert_eq!(clock1.get("hub-2"), 1);
    }

    #[test]
    fn test_vector_clock_compare() {
        let mut clock1 = VectorClock::new();
        clock1.increment("hub-1");

        let mut clock2 = VectorClock::new();
        clock2.increment("hub-1");
        clock2.increment("hub-1");

        assert_eq!(clock1.compare(&clock2), VectorClockOrdering::HappensBefore);
        assert_eq!(clock2.compare(&clock1), VectorClockOrdering::HappensAfter);

        let mut clock3 = VectorClock::new();
        clock3.increment("hub-2");

        assert_eq!(clock1.compare(&clock3), VectorClockOrdering::Concurrent);
    }

    #[test]
    fn test_lww_register() {
        let mut reg1 = LWWRegister::new(10, "hub-1".to_string());

        // Later write should win
        std::thread::sleep(std::time::Duration::from_millis(10));
        reg1.update(20, current_timestamp(), "hub-2".to_string());
        assert_eq!(reg1.value, 20);

        // Earlier write should lose
        reg1.update(5, reg1.timestamp - 100, "hub-3".to_string());
        assert_eq!(reg1.value, 20);
    }

    #[test]
    fn test_g_counter() {
        let mut counter1 = GCounter::new();
        counter1.increment("hub-1");
        counter1.increment("hub-1");

        let mut counter2 = GCounter::new();
        counter2.increment("hub-2");
        counter2.increment_by("hub-2", 5);

        counter1.merge(&counter2);

        assert_eq!(counter1.value(), 8); // 2 + 6
    }

    #[test]
    fn test_or_set() {
        let mut set1 = ORSet::<String>::new();
        set1.add("room-1".to_string(), "hub-1");
        set1.add("room-2".to_string(), "hub-1");

        assert!(set1.contains(&"room-1".to_string()));
        assert!(set1.contains(&"room-2".to_string()));

        set1.remove(&"room-1".to_string());
        assert!(!set1.contains(&"room-1".to_string()));
        assert!(set1.contains(&"room-2".to_string()));
    }

    #[test]
    fn test_or_set_merge() {
        let mut set1 = ORSet::<String>::new();
        set1.add("room-1".to_string(), "hub-1");

        let mut set2 = ORSet::<String>::new();
        set2.add("room-2".to_string(), "hub-2");

        set1.merge(&set2);

        assert!(set1.contains(&"room-1".to_string()));
        assert!(set1.contains(&"room-2".to_string()));
    }

    #[test]
    fn test_crdt_state_merge() {
        let mut state1 = CRDTState::new("hub-1".to_string());
        state1.active_rooms.add("living-room".to_string(), "hub-1");

        let mut state2 = CRDTState::new("hub-2".to_string());
        state2.active_rooms.add("kitchen".to_string(), "hub-2");

        state1.merge(&state2);

        let rooms = state1.active_rooms.values();
        assert!(rooms.contains(&"living-room".to_string()));
        assert!(rooms.contains(&"kitchen".to_string()));
    }
}

/*
 * 鏡
 * State flows. CRDTs merge. Conflicts resolve. The mesh stays consistent.
 */
