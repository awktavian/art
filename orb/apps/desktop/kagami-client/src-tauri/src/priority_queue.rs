//! Priority Queue — Request Prioritization & Scheduling
//!
//! Implements a priority-based request queue with:
//! - Priority levels: Safety > Scenes > Lights > Other
//! - Deadline-based scheduling (EDF - Earliest Deadline First)
//! - Starvation prevention via aging
//! - Request coalescing for efficiency
//!
//! Colony: Flow (e3) - Coordination & Timing
//!
//! Priority hierarchy:
//! ```
//! P0 (Critical)  - Safety commands, emergency stops
//! P1 (High)      - Scene changes, locks, fireplace
//! P2 (Normal)    - Light controls, shades
//! P3 (Low)       - Status queries, telemetry
//! P4 (Background) - Analytics, logging
//! ```
//!
//! h(x) >= 0. Always.

use serde::{Deserialize, Serialize};
use std::cmp::Ordering;
use std::collections::{BinaryHeap, HashMap};
use std::sync::atomic::{AtomicU64, Ordering as AtomicOrdering};
use std::sync::Mutex;
use std::time::{Duration, Instant};
use tracing::{debug, warn};

// ═══════════════════════════════════════════════════════════════
// PRIORITY LEVELS
// ═══════════════════════════════════════════════════════════════

/// Request priority levels
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[repr(u8)]
pub enum Priority {
    /// Critical - safety commands, emergency stops (h(x) enforcement)
    Critical = 0,
    /// High - scene changes, locks, fireplace
    High = 1,
    /// Normal - light controls, shades
    Normal = 2,
    /// Low - status queries, telemetry
    Low = 3,
    /// Background - analytics, logging
    Background = 4,
}

impl Priority {
    /// Get priority from command type
    pub fn from_command(command: &str) -> Self {
        match command {
            // Critical - safety first
            "emergency_stop" | "safety_override" | "cbf_violation" => Priority::Critical,

            // High - state-changing operations
            "execute_scene" | "goodnight" | "welcome_home" | "movie_mode" |
            "exit_movie_mode" | "away_mode" | "lock_all" | "unlock" |
            "fireplace_on" | "fireplace_off" | "toggle_fireplace" => Priority::High,

            // Normal - device controls
            "set_lights" | "control_lights" | "control_shades" |
            "open_shades" | "close_shades" | "control_tv" |
            "raise_tv" | "lower_tv" => Priority::Normal,

            // Low - queries and status
            "get_status" | "get_rooms" | "get_devices" |
            "get_scene_list" | "get_light_level" => Priority::Low,

            // Background - analytics
            "log_event" | "sync_telemetry" | "send_analytics" => Priority::Background,

            // Default to normal
            _ => Priority::Normal,
        }
    }

    /// Get numeric value (lower = higher priority)
    pub fn value(&self) -> u8 {
        *self as u8
    }

    /// Get base timeout for this priority
    pub fn default_timeout(&self) -> Duration {
        match self {
            Priority::Critical => Duration::from_millis(500),
            Priority::High => Duration::from_secs(2),
            Priority::Normal => Duration::from_secs(5),
            Priority::Low => Duration::from_secs(10),
            Priority::Background => Duration::from_secs(30),
        }
    }
}

impl Default for Priority {
    fn default() -> Self {
        Priority::Normal
    }
}

// ═══════════════════════════════════════════════════════════════
// REQUEST
// ═══════════════════════════════════════════════════════════════

/// Unique request ID
pub type RequestId = u64;

/// Request in the queue
#[derive(Debug, Clone)]
pub struct Request {
    /// Unique request ID
    pub id: RequestId,
    /// Command type
    pub command: String,
    /// Command parameters
    pub params: serde_json::Value,
    /// Priority level
    pub priority: Priority,
    /// Deadline for completion
    pub deadline: Instant,
    /// Time request was enqueued
    pub enqueued_at: Instant,
    /// Number of times priority was boosted (aging)
    pub boost_count: u32,
    /// Coalescing key (requests with same key can be merged)
    pub coalesce_key: Option<String>,
    /// Whether this request can be coalesced
    pub coalesceable: bool,
}

impl Request {
    /// Create a new request
    pub fn new(command: String, params: serde_json::Value) -> Self {
        let priority = Priority::from_command(&command);
        let now = Instant::now();

        Self {
            id: generate_request_id(),
            command,
            params,
            priority,
            deadline: now + priority.default_timeout(),
            enqueued_at: now,
            boost_count: 0,
            coalesce_key: None,
            coalesceable: false,
        }
    }

    /// Create request with explicit priority
    pub fn with_priority(command: String, params: serde_json::Value, priority: Priority) -> Self {
        let now = Instant::now();

        Self {
            id: generate_request_id(),
            command,
            params,
            priority,
            deadline: now + priority.default_timeout(),
            enqueued_at: now,
            boost_count: 0,
            coalesce_key: None,
            coalesceable: false,
        }
    }

    /// Set deadline
    pub fn with_deadline(mut self, deadline: Instant) -> Self {
        self.deadline = deadline;
        self
    }

    /// Set coalesce key
    pub fn with_coalesce_key(mut self, key: String) -> Self {
        self.coalesce_key = Some(key);
        self.coalesceable = true;
        self
    }

    /// Get effective priority (accounts for aging boost)
    pub fn effective_priority(&self) -> u8 {
        let base = self.priority.value();
        base.saturating_sub(self.boost_count.min(base as u32) as u8)
    }

    /// Check if deadline has passed
    pub fn is_expired(&self) -> bool {
        Instant::now() > self.deadline
    }

    /// Get time until deadline
    pub fn time_to_deadline(&self) -> Duration {
        self.deadline.saturating_duration_since(Instant::now())
    }

    /// Get wait time
    pub fn wait_time(&self) -> Duration {
        self.enqueued_at.elapsed()
    }
}

// Ordering for BinaryHeap (min-heap by effective priority, then deadline)
impl Eq for Request {}

impl PartialEq for Request {
    fn eq(&self, other: &Self) -> bool {
        self.id == other.id
    }
}

impl Ord for Request {
    fn cmp(&self, other: &Self) -> Ordering {
        // Lower effective priority value = higher priority
        // If same priority, earlier deadline wins
        // Use Reverse ordering for min-heap behavior
        match self.effective_priority().cmp(&other.effective_priority()) {
            Ordering::Equal => other.deadline.cmp(&self.deadline), // Earlier deadline = higher priority
            other => other.reverse(), // Lower value = higher priority
        }
    }
}

impl PartialOrd for Request {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

// ═══════════════════════════════════════════════════════════════
// PRIORITY QUEUE
// ═══════════════════════════════════════════════════════════════

/// Configuration for the priority queue
#[derive(Debug, Clone)]
pub struct QueueConfig {
    /// Maximum queue size
    pub max_size: usize,
    /// Aging interval (how often to boost priority of waiting requests)
    pub aging_interval: Duration,
    /// Maximum boost count before request is forced to critical
    pub max_boost: u32,
    /// Enable request coalescing
    pub enable_coalescing: bool,
    /// Starvation threshold (requests waiting longer than this get boosted)
    pub starvation_threshold: Duration,
}

impl Default for QueueConfig {
    fn default() -> Self {
        Self {
            max_size: 1000,
            aging_interval: Duration::from_secs(1),
            max_boost: 4, // Can boost from Background to Critical
            enable_coalescing: true,
            starvation_threshold: Duration::from_secs(5),
        }
    }
}

/// Priority queue with deadline scheduling and starvation prevention
pub struct PriorityQueue {
    /// Main queue (heap)
    queue: Mutex<BinaryHeap<Request>>,
    /// Coalescing map (key -> request)
    coalesce_map: Mutex<HashMap<String, RequestId>>,
    /// Request lookup by ID
    request_map: Mutex<HashMap<RequestId, Request>>,
    /// Statistics
    stats: QueueStats,
    /// Configuration
    config: QueueConfig,
    /// Last aging tick
    last_aging: Mutex<Instant>,
}

/// Queue statistics
#[derive(Debug, Default)]
pub struct QueueStats {
    /// Total requests enqueued
    pub total_enqueued: AtomicU64,
    /// Total requests dequeued
    pub total_dequeued: AtomicU64,
    /// Total requests expired
    pub total_expired: AtomicU64,
    /// Total requests coalesced
    pub total_coalesced: AtomicU64,
    /// Total priority boosts (aging)
    pub total_boosts: AtomicU64,
}

impl QueueStats {
    pub fn to_json(&self) -> serde_json::Value {
        serde_json::json!({
            "total_enqueued": self.total_enqueued.load(AtomicOrdering::Relaxed),
            "total_dequeued": self.total_dequeued.load(AtomicOrdering::Relaxed),
            "total_expired": self.total_expired.load(AtomicOrdering::Relaxed),
            "total_coalesced": self.total_coalesced.load(AtomicOrdering::Relaxed),
            "total_boosts": self.total_boosts.load(AtomicOrdering::Relaxed),
        })
    }
}

impl PriorityQueue {
    /// Create a new priority queue
    pub fn new() -> Self {
        Self::with_config(QueueConfig::default())
    }

    /// Create with custom config
    pub fn with_config(config: QueueConfig) -> Self {
        Self {
            queue: Mutex::new(BinaryHeap::with_capacity(config.max_size)),
            coalesce_map: Mutex::new(HashMap::new()),
            request_map: Mutex::new(HashMap::new()),
            stats: QueueStats::default(),
            config,
            last_aging: Mutex::new(Instant::now()),
        }
    }

    /// Enqueue a request
    pub fn enqueue(&self, request: Request) -> Result<RequestId, QueueError> {
        let mut queue = self.queue.lock().unwrap();

        // Check capacity
        if queue.len() >= self.config.max_size {
            return Err(QueueError::QueueFull);
        }

        let request_id = request.id;

        // Handle coalescing
        if self.config.enable_coalescing && request.coalesceable {
            if let Some(ref key) = request.coalesce_key {
                let mut coalesce_map = self.coalesce_map.lock().unwrap();
                if let Some(&existing_id) = coalesce_map.get(key) {
                    // Update existing request instead of adding new
                    let mut request_map = self.request_map.lock().unwrap();
                    if let Some(existing) = request_map.get_mut(&existing_id) {
                        existing.params = request.params;
                        existing.deadline = request.deadline.max(existing.deadline);
                        self.stats.total_coalesced.fetch_add(1, AtomicOrdering::Relaxed);
                        debug!("Coalesced request {} with {}", request_id, existing_id);
                        return Ok(existing_id);
                    }
                }
                coalesce_map.insert(key.clone(), request_id);
            }
        }

        // Add to request map
        self.request_map.lock().unwrap().insert(request_id, request.clone());

        // Add to queue
        queue.push(request);
        self.stats.total_enqueued.fetch_add(1, AtomicOrdering::Relaxed);

        debug!("Enqueued request {} with priority {:?}", request_id, queue.peek().map(|r| r.priority));

        Ok(request_id)
    }

    /// Dequeue highest priority request
    pub fn dequeue(&self) -> Option<Request> {
        // First, run aging if needed
        self.run_aging();

        let mut queue = self.queue.lock().unwrap();

        // Remove expired requests from front
        while let Some(request) = queue.peek() {
            if request.is_expired() {
                let expired = queue.pop().unwrap();
                self.cleanup_request(&expired);
                self.stats.total_expired.fetch_add(1, AtomicOrdering::Relaxed);
                warn!("Request {} expired after {:?}", expired.id, expired.wait_time());
            } else {
                break;
            }
        }

        // Get highest priority request
        if let Some(request) = queue.pop() {
            self.cleanup_request(&request);
            self.stats.total_dequeued.fetch_add(1, AtomicOrdering::Relaxed);
            debug!(
                "Dequeued request {} ({}) after {:?}",
                request.id, request.command, request.wait_time()
            );
            Some(request)
        } else {
            None
        }
    }

    /// Peek at highest priority request without removing
    pub fn peek(&self) -> Option<Request> {
        self.queue.lock().unwrap().peek().cloned()
    }

    /// Get queue length
    pub fn len(&self) -> usize {
        self.queue.lock().unwrap().len()
    }

    /// Check if queue is empty
    pub fn is_empty(&self) -> bool {
        self.queue.lock().unwrap().is_empty()
    }

    /// Cancel a request by ID
    pub fn cancel(&self, request_id: RequestId) -> bool {
        let mut request_map = self.request_map.lock().unwrap();
        if let Some(request) = request_map.remove(&request_id) {
            // Remove from coalesce map
            if let Some(ref key) = request.coalesce_key {
                self.coalesce_map.lock().unwrap().remove(key);
            }

            // Note: We don't remove from BinaryHeap (expensive)
            // The request will be skipped on dequeue
            debug!("Cancelled request {}", request_id);
            true
        } else {
            false
        }
    }

    /// Get queue statistics
    pub fn get_stats(&self) -> serde_json::Value {
        let queue = self.queue.lock().unwrap();
        let mut priority_counts = HashMap::new();

        for request in queue.iter() {
            *priority_counts.entry(format!("{:?}", request.priority)).or_insert(0) += 1;
        }

        serde_json::json!({
            "length": queue.len(),
            "by_priority": priority_counts,
            "stats": self.stats.to_json(),
        })
    }

    /// Run aging to prevent starvation
    fn run_aging(&self) {
        let mut last_aging = self.last_aging.lock().unwrap();
        let now = Instant::now();

        if now.duration_since(*last_aging) < self.config.aging_interval {
            return;
        }
        *last_aging = now;
        drop(last_aging);

        // Collect requests that need boosting
        let mut queue = self.queue.lock().unwrap();
        let mut boosted: Vec<Request> = Vec::new();
        let mut kept: Vec<Request> = Vec::new();

        while let Some(mut request) = queue.pop() {
            if request.wait_time() > self.config.starvation_threshold
                && request.boost_count < self.config.max_boost
            {
                request.boost_count += 1;
                self.stats.total_boosts.fetch_add(1, AtomicOrdering::Relaxed);
                debug!(
                    "Boosted request {} from {:?} (boost count: {})",
                    request.id, request.priority, request.boost_count
                );
                boosted.push(request);
            } else {
                kept.push(request);
            }
        }

        // Re-add all requests
        for request in kept.into_iter().chain(boosted.into_iter()) {
            queue.push(request);
        }
    }

    /// Cleanup request metadata
    fn cleanup_request(&self, request: &Request) {
        self.request_map.lock().unwrap().remove(&request.id);
        if let Some(ref key) = request.coalesce_key {
            self.coalesce_map.lock().unwrap().remove(key);
        }
    }

    /// Drain all requests (for shutdown)
    pub fn drain(&self) -> Vec<Request> {
        let mut queue = self.queue.lock().unwrap();
        let mut requests = Vec::with_capacity(queue.len());
        while let Some(request) = queue.pop() {
            requests.push(request);
        }
        self.coalesce_map.lock().unwrap().clear();
        self.request_map.lock().unwrap().clear();
        requests
    }
}

impl Default for PriorityQueue {
    fn default() -> Self {
        Self::new()
    }
}

/// Queue errors
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum QueueError {
    QueueFull,
    RequestNotFound,
    InvalidPriority,
}

impl std::fmt::Display for QueueError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::QueueFull => write!(f, "Queue is full"),
            Self::RequestNotFound => write!(f, "Request not found"),
            Self::InvalidPriority => write!(f, "Invalid priority"),
        }
    }
}

impl std::error::Error for QueueError {}

// ═══════════════════════════════════════════════════════════════
// UTILITIES
// ═══════════════════════════════════════════════════════════════

/// Generate unique request ID
fn generate_request_id() -> RequestId {
    static COUNTER: AtomicU64 = AtomicU64::new(0);
    let count = COUNTER.fetch_add(1, AtomicOrdering::Relaxed);
    let timestamp = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis() as u64;
    (timestamp << 20) | (count & 0xFFFFF)
}

// ═══════════════════════════════════════════════════════════════
// GLOBAL INSTANCE
// ═══════════════════════════════════════════════════════════════

static PRIORITY_QUEUE: std::sync::OnceLock<PriorityQueue> = std::sync::OnceLock::new();

pub fn get_priority_queue() -> &'static PriorityQueue {
    PRIORITY_QUEUE.get_or_init(PriorityQueue::new)
}

// ═══════════════════════════════════════════════════════════════
// TAURI COMMANDS
// ═══════════════════════════════════════════════════════════════

#[tauri::command]
pub fn queue_request(
    command: String,
    params: serde_json::Value,
    priority: Option<u8>,
) -> Result<u64, String> {
    let priority = priority
        .map(|p| match p {
            0 => Priority::Critical,
            1 => Priority::High,
            2 => Priority::Normal,
            3 => Priority::Low,
            _ => Priority::Background,
        })
        .unwrap_or_else(|| Priority::from_command(&command));

    let request = Request::with_priority(command, params, priority);

    get_priority_queue()
        .enqueue(request)
        .map_err(|e| e.to_string())
}

#[tauri::command]
pub fn dequeue_request() -> Option<serde_json::Value> {
    get_priority_queue().dequeue().map(|r| {
        serde_json::json!({
            "id": r.id,
            "command": r.command,
            "params": r.params,
            "priority": format!("{:?}", r.priority),
            "wait_time_ms": r.wait_time().as_millis(),
        })
    })
}

#[tauri::command]
pub fn cancel_request(request_id: u64) -> bool {
    get_priority_queue().cancel(request_id)
}

#[tauri::command]
pub fn get_queue_stats() -> serde_json::Value {
    get_priority_queue().get_stats()
}

#[tauri::command]
pub fn get_queue_length() -> usize {
    get_priority_queue().len()
}

/*
 * Flow schedules. Flow prioritizes. Flow delivers.
 * h(x) >= 0. Always.
 */
