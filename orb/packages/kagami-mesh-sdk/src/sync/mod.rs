//! Synchronization primitives for distributed state management.
//!
//! This module provides CRDT (Conflict-free Replicated Data Types) implementations
//! and vector clocks for causality tracking in the Kagami mesh network.

mod crdt;
mod vector_clock;

pub use crdt::{CrdtError, GCounter, LwwRegister, OrSet};
pub use vector_clock::{VectorClock, VectorClockOrdering};
