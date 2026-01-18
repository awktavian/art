//! Vector clock implementation for causality tracking.
//!
//! Vector clocks are used to establish a partial ordering of events in a
//! distributed system. Each node maintains a logical clock, and the vector
//! of all clocks allows us to determine happens-before relationships.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// The type used for node identifiers in the vector clock.
pub type NodeId = String;

/// The type used for clock values.
pub type ClockValue = u64;

/// Comparison result between two vector clocks.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum VectorClockOrdering {
    /// The first clock happened before the second.
    HappensBefore,

    /// The second clock happened before the first.
    HappensAfter,

    /// The clocks are concurrent (neither happened before the other).
    Concurrent,

    /// The clocks are identical.
    Equal,
}

/// A vector clock for tracking causality in distributed systems.
///
/// Each entry maps a node ID to its logical clock value. The vector clock
/// can be incremented, merged with others, and compared for causality.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VectorClock {
    /// Map of node ID to clock value.
    clocks: HashMap<NodeId, ClockValue>,
}

impl Default for VectorClock {
    fn default() -> Self {
        Self::new()
    }
}

impl VectorClock {
    /// Create a new empty vector clock.
    pub fn new() -> Self {
        Self {
            clocks: HashMap::new(),
        }
    }

    /// Create a vector clock with an initial node.
    pub fn with_node(node_id: impl Into<NodeId>) -> Self {
        let mut vc = Self::new();
        vc.clocks.insert(node_id.into(), 0);
        vc
    }

    /// Get the clock value for a node.
    pub fn get(&self, node_id: &str) -> ClockValue {
        self.clocks.get(node_id).copied().unwrap_or(0)
    }

    /// Increment the clock for a node.
    ///
    /// This should be called when the node performs a local event.
    pub fn increment(&mut self, node_id: impl Into<NodeId>) {
        let node_id = node_id.into();
        let counter = self.clocks.entry(node_id).or_insert(0);
        *counter += 1;
    }

    /// Increment and return a new vector clock (functional style).
    pub fn incremented(&self, node_id: impl Into<NodeId>) -> Self {
        let mut new_vc = self.clone();
        new_vc.increment(node_id);
        new_vc
    }

    /// Update the clock for a node to a specific value.
    ///
    /// Only updates if the new value is greater than the current value.
    pub fn update(&mut self, node_id: impl Into<NodeId>, value: ClockValue) {
        let node_id = node_id.into();
        let current = self.clocks.entry(node_id).or_insert(0);
        if value > *current {
            *current = value;
        }
    }

    /// Merge with another vector clock.
    ///
    /// Takes the maximum value for each node from both clocks.
    /// Optimized to only clone node_id when inserting a new entry.
    pub fn merge(&mut self, other: &VectorClock) {
        for (node_id, &value) in &other.clocks {
            match self.clocks.get_mut(node_id) {
                Some(current) if value > *current => *current = value,
                Some(_) => {} // value <= current, no update needed
                None => {
                    self.clocks.insert(node_id.clone(), value);
                }
            }
        }
    }

    /// Merge and return a new vector clock (functional style).
    pub fn merged(&self, other: &VectorClock) -> Self {
        let mut new_vc = self.clone();
        new_vc.merge(other);
        new_vc
    }

    /// Compare this vector clock with another.
    ///
    /// Returns the causal relationship between the two clocks.
    pub fn compare(&self, other: &VectorClock) -> VectorClockOrdering {
        let all_nodes: std::collections::HashSet<&String> =
            self.clocks.keys().chain(other.clocks.keys()).collect();

        let mut self_less = false;
        let mut other_less = false;

        for node_id in all_nodes {
            let self_val = self.get(node_id);
            let other_val = other.get(node_id);

            match self_val.cmp(&other_val) {
                std::cmp::Ordering::Less => self_less = true,
                std::cmp::Ordering::Greater => other_less = true,
                std::cmp::Ordering::Equal => {}
            }

            // Early exit if we've determined concurrency
            if self_less && other_less {
                return VectorClockOrdering::Concurrent;
            }
        }

        match (self_less, other_less) {
            (false, false) => VectorClockOrdering::Equal,
            (true, false) => VectorClockOrdering::HappensBefore,
            (false, true) => VectorClockOrdering::HappensAfter,
            (true, true) => VectorClockOrdering::Concurrent,
        }
    }

    /// Check if this clock happened before another.
    pub fn happened_before(&self, other: &VectorClock) -> bool {
        matches!(self.compare(other), VectorClockOrdering::HappensBefore)
    }

    /// Check if this clock happened after another.
    pub fn happened_after(&self, other: &VectorClock) -> bool {
        matches!(self.compare(other), VectorClockOrdering::HappensAfter)
    }

    /// Check if this clock is concurrent with another.
    pub fn is_concurrent(&self, other: &VectorClock) -> bool {
        matches!(self.compare(other), VectorClockOrdering::Concurrent)
    }

    /// Check if two clocks are equal.
    pub fn is_equal(&self, other: &VectorClock) -> bool {
        matches!(self.compare(other), VectorClockOrdering::Equal)
    }

    /// Get all node IDs in this vector clock.
    pub fn nodes(&self) -> impl Iterator<Item = &NodeId> {
        self.clocks.keys()
    }

    /// Get the total number of nodes tracked.
    pub fn node_count(&self) -> usize {
        self.clocks.len()
    }

    /// Get the sum of all clock values (useful for debugging).
    pub fn sum(&self) -> ClockValue {
        self.clocks.values().sum()
    }

    /// Check if the clock is empty (no events recorded).
    pub fn is_empty(&self) -> bool {
        self.clocks.is_empty() || self.clocks.values().all(|&v| v == 0)
    }

    /// Convert to a sorted vector of (node_id, value) pairs.
    pub fn to_sorted_vec(&self) -> Vec<(NodeId, ClockValue)> {
        let mut entries: Vec<_> = self.clocks.clone().into_iter().collect();
        entries.sort_by(|a, b| a.0.cmp(&b.0));
        entries
    }
}

impl PartialEq for VectorClock {
    fn eq(&self, other: &Self) -> bool {
        self.is_equal(other)
    }
}

impl Eq for VectorClock {}

impl std::fmt::Display for VectorClock {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let entries = self.to_sorted_vec();
        let pairs: Vec<String> = entries.iter().map(|(k, v)| format!("{}:{}", k, v)).collect();
        write!(f, "VC({})", pairs.join(", "))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_empty_clock() {
        let vc = VectorClock::new();
        assert!(vc.is_empty());
        assert_eq!(vc.get("node1"), 0);
    }

    #[test]
    fn test_increment() {
        let mut vc = VectorClock::new();
        vc.increment("node1");
        assert_eq!(vc.get("node1"), 1);

        vc.increment("node1");
        assert_eq!(vc.get("node1"), 2);

        vc.increment("node2");
        assert_eq!(vc.get("node2"), 1);
    }

    #[test]
    fn test_merge() {
        let mut vc1 = VectorClock::new();
        vc1.increment("A");
        vc1.increment("A");
        vc1.increment("B");

        let mut vc2 = VectorClock::new();
        vc2.increment("A");
        vc2.increment("C");
        vc2.increment("C");

        vc1.merge(&vc2);

        assert_eq!(vc1.get("A"), 2); // Max of 2 and 1
        assert_eq!(vc1.get("B"), 1); // Only in vc1
        assert_eq!(vc1.get("C"), 2); // Only in vc2
    }

    #[test]
    fn test_compare_equal() {
        let mut vc1 = VectorClock::new();
        vc1.increment("A");
        vc1.increment("B");

        let mut vc2 = VectorClock::new();
        vc2.increment("A");
        vc2.increment("B");

        assert_eq!(vc1.compare(&vc2), VectorClockOrdering::Equal);
    }

    #[test]
    fn test_compare_happens_before() {
        let mut vc1 = VectorClock::new();
        vc1.increment("A");

        let mut vc2 = VectorClock::new();
        vc2.increment("A");
        vc2.increment("A");
        vc2.increment("B");

        assert_eq!(vc1.compare(&vc2), VectorClockOrdering::HappensBefore);
        assert!(vc1.happened_before(&vc2));
        assert!(vc2.happened_after(&vc1));
    }

    #[test]
    fn test_compare_concurrent() {
        let mut vc1 = VectorClock::new();
        vc1.increment("A");
        vc1.increment("A");

        let mut vc2 = VectorClock::new();
        vc2.increment("B");
        vc2.increment("B");

        assert_eq!(vc1.compare(&vc2), VectorClockOrdering::Concurrent);
        assert!(vc1.is_concurrent(&vc2));
    }

    #[test]
    fn test_concurrent_partial() {
        // vc1: A=2, B=1
        let mut vc1 = VectorClock::new();
        vc1.increment("A");
        vc1.increment("A");
        vc1.increment("B");

        // vc2: A=1, B=2
        let mut vc2 = VectorClock::new();
        vc2.increment("A");
        vc2.increment("B");
        vc2.increment("B");

        // Neither happens before the other
        assert_eq!(vc1.compare(&vc2), VectorClockOrdering::Concurrent);
    }

    #[test]
    fn test_incremented_functional() {
        let vc1 = VectorClock::with_node("A");
        let vc2 = vc1.incremented("A");

        assert_eq!(vc1.get("A"), 0);
        assert_eq!(vc2.get("A"), 1);
    }

    #[test]
    fn test_merged_functional() {
        let mut vc1 = VectorClock::new();
        vc1.increment("A");

        let mut vc2 = VectorClock::new();
        vc2.increment("B");

        let vc3 = vc1.merged(&vc2);

        assert_eq!(vc1.get("B"), 0); // vc1 unchanged
        assert_eq!(vc3.get("A"), 1);
        assert_eq!(vc3.get("B"), 1);
    }

    #[test]
    fn test_display() {
        let mut vc = VectorClock::new();
        vc.increment("A");
        vc.increment("B");
        vc.increment("B");

        let s = format!("{}", vc);
        assert!(s.contains("A:1"));
        assert!(s.contains("B:2"));
    }

    #[test]
    fn test_serialization() {
        let mut vc = VectorClock::new();
        vc.increment("node1");
        vc.increment("node2");

        let json = serde_json::to_string(&vc).unwrap();
        let recovered: VectorClock = serde_json::from_str(&json).unwrap();

        assert_eq!(vc, recovered);
    }
}
