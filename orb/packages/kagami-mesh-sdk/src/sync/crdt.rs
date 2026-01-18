//! CRDT (Conflict-free Replicated Data Type) implementations.
//!
//! This module provides three fundamental CRDTs:
//! - LWW-Register: Last-Writer-Wins register for single values
//! - G-Counter: Grow-only counter for distributed counting
//! - OR-Set: Observed-Remove set for distributed set operations

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet};
use std::hash::Hash;
use thiserror::Error;

/// Errors that can occur during CRDT operations.
#[derive(Debug, Error)]
pub enum CrdtError {
    #[error("Invalid operation: {0}")]
    InvalidOperation(String),

    #[error("Serialization error: {0}")]
    SerializationError(String),
}

// ============================================================================
// LWW-Register (Last-Writer-Wins Register)
// ============================================================================

/// A Last-Writer-Wins Register.
///
/// This CRDT stores a single value and uses timestamps to resolve conflicts.
/// When two concurrent writes occur, the one with the higher timestamp wins.
/// If timestamps are equal, the tie is broken deterministically by value comparison.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LwwRegister<T>
where
    T: Clone + Serialize + PartialOrd,
{
    /// The current value.
    value: T,

    /// Timestamp when this value was written.
    timestamp: DateTime<Utc>,

    /// Node ID that wrote this value (for tie-breaking).
    node_id: String,
}

impl<T> LwwRegister<T>
where
    T: Clone + Serialize + PartialOrd,
{
    /// Create a new LWW register with an initial value.
    pub fn new(value: T, node_id: impl Into<String>) -> Self {
        Self {
            value,
            timestamp: Utc::now(),
            node_id: node_id.into(),
        }
    }

    /// Create a new LWW register with a specific timestamp.
    pub fn with_timestamp(value: T, node_id: impl Into<String>, timestamp: DateTime<Utc>) -> Self {
        Self {
            value,
            timestamp,
            node_id: node_id.into(),
        }
    }

    /// Get the current value.
    pub fn value(&self) -> &T {
        &self.value
    }

    /// Get the timestamp of the current value.
    pub fn timestamp(&self) -> DateTime<Utc> {
        self.timestamp
    }

    /// Get the node ID that wrote the current value.
    pub fn node_id(&self) -> &str {
        &self.node_id
    }

    /// Set a new value, updating the timestamp.
    pub fn set(&mut self, value: T, node_id: impl Into<String>) {
        self.value = value;
        self.timestamp = Utc::now();
        self.node_id = node_id.into();
    }

    /// Set a new value with a specific timestamp.
    pub fn set_with_timestamp(
        &mut self,
        value: T,
        node_id: impl Into<String>,
        timestamp: DateTime<Utc>,
    ) {
        self.value = value;
        self.timestamp = timestamp;
        self.node_id = node_id.into();
    }

    /// Merge with another LWW register.
    ///
    /// The register with the higher timestamp wins. If timestamps are equal,
    /// the node ID is used as a tie-breaker.
    pub fn merge(&mut self, other: &LwwRegister<T>) {
        if other.timestamp > self.timestamp
            || (other.timestamp == self.timestamp && other.node_id > self.node_id)
        {
            self.value = other.value.clone();
            self.timestamp = other.timestamp;
            self.node_id = other.node_id.clone();
        }
    }

    /// Merge and return a new register (functional style).
    pub fn merged(&self, other: &LwwRegister<T>) -> Self {
        let mut new_reg = self.clone();
        new_reg.merge(other);
        new_reg
    }
}

impl<T> PartialEq for LwwRegister<T>
where
    T: Clone + Serialize + PartialOrd + PartialEq,
{
    fn eq(&self, other: &Self) -> bool {
        self.value == other.value && self.timestamp == other.timestamp
    }
}

// ============================================================================
// G-Counter (Grow-only Counter)
// ============================================================================

/// A Grow-only Counter.
///
/// This CRDT allows only increment operations. Each node maintains its own
/// counter, and the total is the sum of all node counters. Merging takes
/// the maximum value for each node.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GCounter {
    /// Map of node ID to that node's counter value.
    counters: HashMap<String, u64>,
}

impl Default for GCounter {
    fn default() -> Self {
        Self::new()
    }
}

impl GCounter {
    /// Create a new empty G-Counter.
    pub fn new() -> Self {
        Self {
            counters: HashMap::new(),
        }
    }

    /// Create a G-Counter with an initial value for a node.
    pub fn with_initial(node_id: impl Into<String>, value: u64) -> Self {
        let mut counter = Self::new();
        counter.counters.insert(node_id.into(), value);
        counter
    }

    /// Increment the counter for a node.
    pub fn increment(&mut self, node_id: impl Into<String>) {
        let node_id = node_id.into();
        let counter = self.counters.entry(node_id).or_insert(0);
        *counter += 1;
    }

    /// Increment by a specific amount.
    pub fn increment_by(&mut self, node_id: impl Into<String>, amount: u64) {
        let node_id = node_id.into();
        let counter = self.counters.entry(node_id).or_insert(0);
        *counter += amount;
    }

    /// Get the total count (sum of all node counters).
    pub fn value(&self) -> u64 {
        self.counters.values().sum()
    }

    /// Get the count for a specific node.
    pub fn get(&self, node_id: &str) -> u64 {
        self.counters.get(node_id).copied().unwrap_or(0)
    }

    /// Merge with another G-Counter.
    ///
    /// Takes the maximum value for each node.
    /// Optimized to only clone node_id when inserting a new entry.
    pub fn merge(&mut self, other: &GCounter) {
        for (node_id, &value) in &other.counters {
            match self.counters.get_mut(node_id) {
                Some(current) if value > *current => *current = value,
                Some(_) => {} // value <= current, no update needed
                None => {
                    self.counters.insert(node_id.clone(), value);
                }
            }
        }
    }

    /// Merge and return a new counter (functional style).
    pub fn merged(&self, other: &GCounter) -> Self {
        let mut new_counter = self.clone();
        new_counter.merge(other);
        new_counter
    }

    /// Get all node IDs.
    pub fn nodes(&self) -> impl Iterator<Item = &String> {
        self.counters.keys()
    }

    /// Check if the counter is empty (all zeros).
    pub fn is_empty(&self) -> bool {
        self.value() == 0
    }
}

impl PartialEq for GCounter {
    fn eq(&self, other: &Self) -> bool {
        self.value() == other.value()
    }
}

// ============================================================================
// OR-Set (Observed-Remove Set)
// ============================================================================

/// An element in an OR-Set with its unique tag.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, Hash)]
struct OrSetElement<T>
where
    T: Clone + Eq + Hash,
{
    /// The actual value.
    value: T,

    /// Unique tag for this addition (node_id + sequence number).
    tag: String,
}

/// An Observed-Remove Set.
///
/// This CRDT allows both add and remove operations. Each add creates a unique
/// tag, and remove only removes specific tags. This allows concurrent adds
/// and removes to be resolved correctly.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OrSet<T>
where
    T: Clone + Eq + Hash + Serialize,
{
    /// Set of active elements with their tags.
    elements: HashSet<OrSetElement<T>>,

    /// Counter for generating unique tags per node.
    counters: HashMap<String, u64>,

    /// Tombstones for removed tags (to prevent resurrection).
    tombstones: HashSet<String>,
}

impl<T> Default for OrSet<T>
where
    T: Clone + Eq + Hash + Serialize,
{
    fn default() -> Self {
        Self::new()
    }
}

impl<T> OrSet<T>
where
    T: Clone + Eq + Hash + Serialize,
{
    /// Create a new empty OR-Set.
    pub fn new() -> Self {
        Self {
            elements: HashSet::new(),
            counters: HashMap::new(),
            tombstones: HashSet::new(),
        }
    }

    /// Generate a unique tag for an add operation.
    fn generate_tag(&mut self, node_id: &str) -> String {
        let counter = self.counters.entry(node_id.to_string()).or_insert(0);
        *counter += 1;
        format!("{}:{}", node_id, counter)
    }

    /// Add an element to the set.
    pub fn add(&mut self, value: T, node_id: impl AsRef<str>) {
        let tag = self.generate_tag(node_id.as_ref());
        self.elements.insert(OrSetElement {
            value,
            tag,
        });
    }

    /// Remove an element from the set.
    ///
    /// This removes all instances of the value (all tags).
    pub fn remove(&mut self, value: &T) {
        let tags_to_remove: Vec<String> = self
            .elements
            .iter()
            .filter(|e| &e.value == value)
            .map(|e| e.tag.clone())
            .collect();

        for tag in &tags_to_remove {
            self.tombstones.insert(tag.clone());
        }

        self.elements.retain(|e| &e.value != value);
    }

    /// Check if an element is in the set.
    pub fn contains(&self, value: &T) -> bool {
        self.elements.iter().any(|e| &e.value == value)
    }

    /// Get all values in the set.
    pub fn values(&self) -> Vec<T> {
        let mut seen = HashSet::new();
        self.elements
            .iter()
            .filter(|e| seen.insert(e.value.clone()))
            .map(|e| e.value.clone())
            .collect()
    }

    /// Get the number of unique values in the set.
    pub fn len(&self) -> usize {
        let unique: HashSet<_> = self.elements.iter().map(|e| &e.value).collect();
        unique.len()
    }

    /// Check if the set is empty.
    pub fn is_empty(&self) -> bool {
        self.elements.is_empty()
    }

    /// Merge with another OR-Set.
    ///
    /// Union of elements, minus anything in either's tombstones.
    /// Optimized to minimize allocations during merge.
    pub fn merge(&mut self, other: &OrSet<T>) {
        // Merge tombstones first - only clone tags we don't already have
        for tag in &other.tombstones {
            if !self.tombstones.contains(tag) {
                self.tombstones.insert(tag.clone());
            }
        }

        // Add elements from other that aren't tombstoned
        for element in &other.elements {
            if !self.tombstones.contains(&element.tag) && !self.elements.contains(element) {
                self.elements.insert(element.clone());
            }
        }

        // Remove tombstoned elements from our set
        self.elements
            .retain(|e| !self.tombstones.contains(&e.tag));

        // Merge counters (take max) - only clone node_id for new entries
        for (node_id, &value) in &other.counters {
            match self.counters.get_mut(node_id) {
                Some(current) if value > *current => *current = value,
                Some(_) => {} // value <= current, no update needed
                None => {
                    self.counters.insert(node_id.clone(), value);
                }
            }
        }
    }

    /// Merge and return a new set (functional style).
    pub fn merged(&self, other: &OrSet<T>) -> Self {
        let mut new_set = self.clone();
        new_set.merge(other);
        new_set
    }

    /// Clear all elements from the set.
    pub fn clear(&mut self) {
        for element in &self.elements {
            self.tombstones.insert(element.tag.clone());
        }
        self.elements.clear();
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    // LWW-Register tests
    mod lww_register {
        use super::*;

        #[test]
        fn test_basic_operations() {
            let mut reg = LwwRegister::new(42i32, "node1");
            assert_eq!(*reg.value(), 42);

            reg.set(100, "node1");
            assert_eq!(*reg.value(), 100);
        }

        #[test]
        fn test_merge_later_wins() {
            let reg1 = LwwRegister::new(1i32, "node1");
            std::thread::sleep(std::time::Duration::from_millis(10));
            let reg2 = LwwRegister::new(2i32, "node2");

            let mut merged = reg1.clone();
            merged.merge(&reg2);
            assert_eq!(*merged.value(), 2);
        }

        #[test]
        fn test_merge_same_timestamp_tiebreak() {
            let ts = Utc::now();
            let reg1 = LwwRegister::with_timestamp(1i32, "node1", ts);
            let reg2 = LwwRegister::with_timestamp(2i32, "node2", ts);

            let mut merged = reg1.clone();
            merged.merge(&reg2);
            // node2 > node1, so reg2 wins
            assert_eq!(*merged.value(), 2);
        }
    }

    // G-Counter tests
    mod g_counter {
        use super::*;

        #[test]
        fn test_basic_increment() {
            let mut counter = GCounter::new();
            counter.increment("node1");
            counter.increment("node1");
            counter.increment("node2");

            assert_eq!(counter.value(), 3);
            assert_eq!(counter.get("node1"), 2);
            assert_eq!(counter.get("node2"), 1);
        }

        #[test]
        fn test_merge() {
            let mut c1 = GCounter::new();
            c1.increment("node1");
            c1.increment("node1");

            let mut c2 = GCounter::new();
            c2.increment("node1");
            c2.increment("node2");
            c2.increment("node2");

            c1.merge(&c2);

            assert_eq!(c1.value(), 4);
            assert_eq!(c1.get("node1"), 2); // max(2, 1)
            assert_eq!(c1.get("node2"), 2);
        }

        #[test]
        fn test_merge_is_commutative() {
            let mut c1 = GCounter::with_initial("node1", 5);
            let mut c2 = GCounter::with_initial("node2", 3);

            let merged1 = c1.merged(&c2);
            let merged2 = c2.merged(&c1);

            assert_eq!(merged1.value(), merged2.value());
        }
    }

    // OR-Set tests
    mod or_set {
        use super::*;

        #[test]
        fn test_add_contains() {
            let mut set = OrSet::new();
            set.add("apple", "node1");
            set.add("banana", "node1");

            assert!(set.contains(&"apple"));
            assert!(set.contains(&"banana"));
            assert!(!set.contains(&"cherry"));
        }

        #[test]
        fn test_remove() {
            let mut set = OrSet::new();
            set.add("apple", "node1");
            set.add("banana", "node1");
            set.remove(&"apple");

            assert!(!set.contains(&"apple"));
            assert!(set.contains(&"banana"));
        }

        #[test]
        fn test_concurrent_add_remove() {
            // Simulate concurrent add and remove
            let mut set1 = OrSet::new();
            set1.add("apple", "node1");

            let mut set2 = set1.clone();

            // node1 removes apple
            set1.remove(&"apple");

            // node2 adds apple again (concurrent)
            set2.add("apple", "node2");

            // Merge: the add from node2 should survive
            set1.merge(&set2);

            // node2's add has a different tag, so it survives
            assert!(set1.contains(&"apple"));
        }

        #[test]
        fn test_merge_preserves_concurrent_adds() {
            let mut set1 = OrSet::new();
            set1.add("item", "node1");

            let mut set2 = OrSet::new();
            set2.add("item", "node2");

            set1.merge(&set2);

            assert!(set1.contains(&"item"));
        }

        #[test]
        fn test_values() {
            let mut set = OrSet::new();
            set.add(1, "node1");
            set.add(2, "node1");
            set.add(1, "node2"); // Duplicate value, different tag

            let values = set.values();
            assert_eq!(values.len(), 2);
            assert!(values.contains(&1));
            assert!(values.contains(&2));
        }

        #[test]
        fn test_clear() {
            let mut set = OrSet::new();
            set.add("a", "node1");
            set.add("b", "node1");
            set.clear();

            assert!(set.is_empty());
        }
    }
}
