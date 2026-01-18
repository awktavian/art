//! Telemetry Module — OpenMetrics/Prometheus-compatible metrics export
//!
//! Provides metrics for operational observability:
//! - kagami_wake_false_positive_count: Wake word false positives
//! - kagami_command_success_rate: Command execution success rate
//! - kagami_api_latency_ms: API call latency histogram
//! - kagami_audio_buffer_usage_bytes: Audio buffer usage
//! - kagami_led_render_latency_ms: LED rendering latency
//!
//! Colony: Crystal (e7) - Verification through measurement
//!
//! h(x) >= 0. Always.

use std::collections::HashMap;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, RwLock};
use std::time::{Duration, Instant};
use tracing::{debug, info, warn};

// ============================================================================
// Metric Types
// ============================================================================

/// Counter metric - monotonically increasing value
#[derive(Debug)]
pub struct Counter {
    name: String,
    help: String,
    value: AtomicU64,
    labels: HashMap<String, String>,
}

impl Counter {
    pub fn new(name: &str, help: &str) -> Self {
        Self {
            name: name.to_string(),
            help: help.to_string(),
            value: AtomicU64::new(0),
            labels: HashMap::new(),
        }
    }

    pub fn with_labels(mut self, labels: HashMap<String, String>) -> Self {
        self.labels = labels;
        self
    }

    pub fn inc(&self) {
        self.value.fetch_add(1, Ordering::Relaxed);
    }

    pub fn inc_by(&self, n: u64) {
        self.value.fetch_add(n, Ordering::Relaxed);
    }

    pub fn get(&self) -> u64 {
        self.value.load(Ordering::Relaxed)
    }

    /// Format as OpenMetrics text
    pub fn to_openmetrics(&self) -> String {
        let labels_str = if self.labels.is_empty() {
            String::new()
        } else {
            let pairs: Vec<String> = self.labels
                .iter()
                .map(|(k, v)| format!("{}=\"{}\"", k, v))
                .collect();
            format!("{{{}}}", pairs.join(","))
        };

        format!(
            "# HELP {} {}\n# TYPE {} counter\n{}{} {}\n",
            self.name, self.help, self.name, self.name, labels_str, self.get()
        )
    }
}

/// Gauge metric - value that can go up or down
#[derive(Debug)]
pub struct Gauge {
    name: String,
    help: String,
    value: AtomicU64, // Stored as f64 bits
    labels: HashMap<String, String>,
}

impl Gauge {
    pub fn new(name: &str, help: &str) -> Self {
        Self {
            name: name.to_string(),
            help: help.to_string(),
            value: AtomicU64::new(0),
            labels: HashMap::new(),
        }
    }

    pub fn with_labels(mut self, labels: HashMap<String, String>) -> Self {
        self.labels = labels;
        self
    }

    pub fn set(&self, v: f64) {
        self.value.store(v.to_bits(), Ordering::Relaxed);
    }

    pub fn inc(&self) {
        let current = f64::from_bits(self.value.load(Ordering::Relaxed));
        self.set(current + 1.0);
    }

    pub fn dec(&self) {
        let current = f64::from_bits(self.value.load(Ordering::Relaxed));
        self.set(current - 1.0);
    }

    pub fn get(&self) -> f64 {
        f64::from_bits(self.value.load(Ordering::Relaxed))
    }

    /// Format as OpenMetrics text
    pub fn to_openmetrics(&self) -> String {
        let labels_str = if self.labels.is_empty() {
            String::new()
        } else {
            let pairs: Vec<String> = self.labels
                .iter()
                .map(|(k, v)| format!("{}=\"{}\"", k, v))
                .collect();
            format!("{{{}}}", pairs.join(","))
        };

        format!(
            "# HELP {} {}\n# TYPE {} gauge\n{}{} {}\n",
            self.name, self.help, self.name, self.name, labels_str, self.get()
        )
    }
}

/// Histogram metric - distribution of values with configurable buckets
#[derive(Debug)]
pub struct Histogram {
    name: String,
    help: String,
    buckets: Vec<f64>,
    // @GuardedBy("counts lock") - bucket counts
    counts: RwLock<Vec<AtomicU64>>,
    // @GuardedBy("sum lock") - sum of all observed values
    sum: AtomicU64, // Stored as f64 bits
    // @GuardedBy("total lock") - total observation count
    total: AtomicU64,
    labels: HashMap<String, String>,
}

impl Histogram {
    /// Create histogram with default latency buckets (ms)
    pub fn new_latency(name: &str, help: &str) -> Self {
        // Default latency buckets: 5ms, 10ms, 25ms, 50ms, 100ms, 250ms, 500ms, 1s, 2.5s, 5s, 10s
        let buckets = vec![5.0, 10.0, 25.0, 50.0, 100.0, 250.0, 500.0, 1000.0, 2500.0, 5000.0, 10000.0];
        Self::new(name, help, buckets)
    }

    pub fn new(name: &str, help: &str, buckets: Vec<f64>) -> Self {
        let bucket_count = buckets.len();
        let counts: Vec<AtomicU64> = (0..=bucket_count).map(|_| AtomicU64::new(0)).collect();

        Self {
            name: name.to_string(),
            help: help.to_string(),
            buckets,
            counts: RwLock::new(counts),
            sum: AtomicU64::new(0.0_f64.to_bits()),
            total: AtomicU64::new(0),
            labels: HashMap::new(),
        }
    }

    pub fn with_labels(mut self, labels: HashMap<String, String>) -> Self {
        self.labels = labels;
        self
    }

    /// Observe a value (e.g., latency in ms)
    pub fn observe(&self, v: f64) {
        // Find the bucket
        let bucket_idx = self.buckets
            .iter()
            .position(|&b| v <= b)
            .unwrap_or(self.buckets.len());

        // Increment all buckets from found index to +inf
        if let Ok(counts) = self.counts.read() {
            for i in bucket_idx..counts.len() {
                counts[i].fetch_add(1, Ordering::Relaxed);
            }
        }

        // Update sum
        loop {
            let current = self.sum.load(Ordering::Relaxed);
            let current_f = f64::from_bits(current);
            let new_f = current_f + v;
            if self.sum.compare_exchange(
                current,
                new_f.to_bits(),
                Ordering::Relaxed,
                Ordering::Relaxed,
            ).is_ok() {
                break;
            }
        }

        // Increment total count
        self.total.fetch_add(1, Ordering::Relaxed);
    }

    /// Format as OpenMetrics text
    pub fn to_openmetrics(&self) -> String {
        let mut output = format!(
            "# HELP {} {}\n# TYPE {} histogram\n",
            self.name, self.help, self.name
        );

        let labels_prefix = if self.labels.is_empty() {
            String::new()
        } else {
            let pairs: Vec<String> = self.labels
                .iter()
                .map(|(k, v)| format!("{}=\"{}\"", k, v))
                .collect();
            format!("{},", pairs.join(","))
        };

        // Output bucket lines
        if let Ok(counts) = self.counts.read() {
            for (i, bucket) in self.buckets.iter().enumerate() {
                output.push_str(&format!(
                    "{}_bucket{{{}le=\"{}\"}} {}\n",
                    self.name,
                    labels_prefix,
                    bucket,
                    counts[i].load(Ordering::Relaxed)
                ));
            }
            // +Inf bucket
            output.push_str(&format!(
                "{}_bucket{{{}le=\"+Inf\"}} {}\n",
                self.name,
                labels_prefix,
                counts[self.buckets.len()].load(Ordering::Relaxed)
            ));
        }

        // Sum and count
        let sum = f64::from_bits(self.sum.load(Ordering::Relaxed));
        let count = self.total.load(Ordering::Relaxed);

        output.push_str(&format!(
            "{}_sum{{{}}} {}\n{}_count{{{}}} {}\n",
            self.name, labels_prefix.trim_end_matches(','), sum,
            self.name, labels_prefix.trim_end_matches(','), count
        ));

        output
    }
}

// ============================================================================
// Kagami Hub Metrics Registry
// ============================================================================

/// Hub telemetry metrics registry
pub struct HubMetrics {
    /// Wake word false positive count
    pub wake_false_positive_count: Counter,
    /// Wake word true positive count
    pub wake_true_positive_count: Counter,
    /// Command success count
    pub command_success_count: Counter,
    /// Command failure count
    pub command_failure_count: Counter,
    /// API call latency (ms)
    pub api_latency_ms: Histogram,
    /// Audio buffer usage (bytes)
    pub audio_buffer_usage_bytes: Gauge,
    /// LED render latency (ms)
    pub led_render_latency_ms: Histogram,
    /// Active voice sessions
    pub active_voice_sessions: Gauge,
    /// STT transcription latency (ms)
    pub stt_latency_ms: Histogram,
    /// TTS generation latency (ms)
    pub tts_latency_ms: Histogram,
    /// Speaker identification match rate
    pub speaker_id_match_count: Counter,
    /// Speaker identification miss count
    pub speaker_id_miss_count: Counter,
    /// Circuit breaker state (0=closed, 1=open, 0.5=half-open)
    pub circuit_breaker_state: Gauge,
    /// Device discovery cache hit count
    pub device_cache_hit_count: Counter,
    /// Device discovery cache miss count
    pub device_cache_miss_count: Counter,
    /// NLU confidence histogram
    pub nlu_confidence: Histogram,
    /// Uptime in seconds
    pub uptime_seconds: Gauge,
    /// Start time for uptime calculation
    start_time: Instant,
}

impl HubMetrics {
    /// Create a new metrics registry
    pub fn new() -> Self {
        Self {
            wake_false_positive_count: Counter::new(
                "kagami_wake_false_positive_count",
                "Number of wake word false positives"
            ),
            wake_true_positive_count: Counter::new(
                "kagami_wake_true_positive_count",
                "Number of wake word true positives"
            ),
            command_success_count: Counter::new(
                "kagami_command_success_count",
                "Number of successful command executions"
            ),
            command_failure_count: Counter::new(
                "kagami_command_failure_count",
                "Number of failed command executions"
            ),
            api_latency_ms: Histogram::new_latency(
                "kagami_api_latency_ms",
                "API call latency in milliseconds"
            ),
            audio_buffer_usage_bytes: Gauge::new(
                "kagami_audio_buffer_usage_bytes",
                "Current audio buffer usage in bytes"
            ),
            led_render_latency_ms: Histogram::new_latency(
                "kagami_led_render_latency_ms",
                "LED ring render latency in milliseconds"
            ),
            active_voice_sessions: Gauge::new(
                "kagami_active_voice_sessions",
                "Number of active voice processing sessions"
            ),
            stt_latency_ms: Histogram::new_latency(
                "kagami_stt_latency_ms",
                "Speech-to-text transcription latency in milliseconds"
            ),
            tts_latency_ms: Histogram::new_latency(
                "kagami_tts_latency_ms",
                "Text-to-speech generation latency in milliseconds"
            ),
            speaker_id_match_count: Counter::new(
                "kagami_speaker_id_match_count",
                "Number of successful speaker identifications"
            ),
            speaker_id_miss_count: Counter::new(
                "kagami_speaker_id_miss_count",
                "Number of failed speaker identifications"
            ),
            circuit_breaker_state: Gauge::new(
                "kagami_circuit_breaker_state",
                "Circuit breaker state (0=closed, 0.5=half-open, 1=open)"
            ),
            device_cache_hit_count: Counter::new(
                "kagami_device_cache_hit_count",
                "Number of device discovery cache hits"
            ),
            device_cache_miss_count: Counter::new(
                "kagami_device_cache_miss_count",
                "Number of device discovery cache misses"
            ),
            nlu_confidence: Histogram::new(
                "kagami_nlu_confidence",
                "NLU confidence score distribution",
                vec![0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
            ),
            uptime_seconds: Gauge::new(
                "kagami_uptime_seconds",
                "Hub uptime in seconds"
            ),
            start_time: Instant::now(),
        }
    }

    /// Calculate command success rate
    pub fn command_success_rate(&self) -> f64 {
        let success = self.command_success_count.get() as f64;
        let failure = self.command_failure_count.get() as f64;
        let total = success + failure;
        if total > 0.0 {
            success / total
        } else {
            1.0 // No commands yet, assume 100%
        }
    }

    /// Record a command result
    pub fn record_command_result(&self, success: bool) {
        if success {
            self.command_success_count.inc();
        } else {
            self.command_failure_count.inc();
        }
    }

    /// Record API call latency
    pub fn record_api_latency(&self, duration: Duration) {
        self.api_latency_ms.observe(duration.as_secs_f64() * 1000.0);
    }

    /// Record LED render latency
    pub fn record_led_render_latency(&self, duration: Duration) {
        self.led_render_latency_ms.observe(duration.as_secs_f64() * 1000.0);
    }

    /// Update uptime gauge
    pub fn update_uptime(&self) {
        self.uptime_seconds.set(self.start_time.elapsed().as_secs_f64());
    }

    /// Export all metrics in OpenMetrics/Prometheus text format
    pub fn export_openmetrics(&self) -> String {
        self.update_uptime();

        let mut output = String::new();

        // Add success rate as a derived metric
        let success_rate = self.command_success_rate();
        output.push_str(&format!(
            "# HELP kagami_command_success_rate Command execution success rate (0-1)\n\
             # TYPE kagami_command_success_rate gauge\n\
             kagami_command_success_rate {}\n\n",
            success_rate
        ));

        // Export all metrics
        output.push_str(&self.wake_false_positive_count.to_openmetrics());
        output.push('\n');
        output.push_str(&self.wake_true_positive_count.to_openmetrics());
        output.push('\n');
        output.push_str(&self.command_success_count.to_openmetrics());
        output.push('\n');
        output.push_str(&self.command_failure_count.to_openmetrics());
        output.push('\n');
        output.push_str(&self.api_latency_ms.to_openmetrics());
        output.push('\n');
        output.push_str(&self.audio_buffer_usage_bytes.to_openmetrics());
        output.push('\n');
        output.push_str(&self.led_render_latency_ms.to_openmetrics());
        output.push('\n');
        output.push_str(&self.active_voice_sessions.to_openmetrics());
        output.push('\n');
        output.push_str(&self.stt_latency_ms.to_openmetrics());
        output.push('\n');
        output.push_str(&self.tts_latency_ms.to_openmetrics());
        output.push('\n');
        output.push_str(&self.speaker_id_match_count.to_openmetrics());
        output.push('\n');
        output.push_str(&self.speaker_id_miss_count.to_openmetrics());
        output.push('\n');
        output.push_str(&self.circuit_breaker_state.to_openmetrics());
        output.push('\n');
        output.push_str(&self.device_cache_hit_count.to_openmetrics());
        output.push('\n');
        output.push_str(&self.device_cache_miss_count.to_openmetrics());
        output.push('\n');
        output.push_str(&self.nlu_confidence.to_openmetrics());
        output.push('\n');
        output.push_str(&self.uptime_seconds.to_openmetrics());

        // OpenMetrics EOF marker
        output.push_str("\n# EOF\n");

        output
    }
}

impl Default for HubMetrics {
    fn default() -> Self {
        Self::new()
    }
}

// ============================================================================
// Global Metrics Instance
// ============================================================================

use std::sync::OnceLock;

/// Global metrics registry
static METRICS: OnceLock<HubMetrics> = OnceLock::new();

/// Initialize the global metrics registry
pub fn init() {
    let _ = METRICS.set(HubMetrics::new());
    info!("Telemetry metrics initialized");
}

/// Get the global metrics registry
pub fn metrics() -> &'static HubMetrics {
    METRICS.get_or_init(HubMetrics::new)
}

/// Export metrics in OpenMetrics format (for /metrics endpoint)
pub fn export() -> String {
    metrics().export_openmetrics()
}

// ============================================================================
// Convenience Functions
// ============================================================================

/// Record a wake word detection event
pub fn record_wake_detection(true_positive: bool) {
    if true_positive {
        metrics().wake_true_positive_count.inc();
    } else {
        metrics().wake_false_positive_count.inc();
    }
}

/// Record command execution result
pub fn record_command(success: bool) {
    metrics().record_command_result(success);
}

/// Record API latency
pub fn record_api_call(duration: Duration) {
    metrics().record_api_latency(duration);
}

/// Record LED render time
pub fn record_led_render(duration: Duration) {
    metrics().record_led_render_latency(duration);
}

/// Record LED render time from milliseconds
pub fn record_led_render_ms(duration_ms: u64) {
    metrics().led_render_latency_ms.observe(duration_ms as f64);
}

/// Record NLU inference result with latency and confidence
pub fn record_nlu_inference(duration_ms: u64, confidence: f64) {
    // Record STT/NLU latency
    metrics().stt_latency_ms.observe(duration_ms as f64);
    // Record confidence score
    metrics().nlu_confidence.observe(confidence);
}

/// Update audio buffer size
pub fn set_audio_buffer_size(bytes: usize) {
    metrics().audio_buffer_usage_bytes.set(bytes as f64);
}

/// Record speaker identification result
pub fn record_speaker_id(matched: bool) {
    if matched {
        metrics().speaker_id_match_count.inc();
    } else {
        metrics().speaker_id_miss_count.inc();
    }
}

/// Record NLU confidence
pub fn record_nlu_confidence(confidence: f64) {
    metrics().nlu_confidence.observe(confidence);
}

/// Set circuit breaker state
pub fn set_circuit_breaker_state(state: CircuitBreakerState) {
    let value = match state {
        CircuitBreakerState::Closed => 0.0,
        CircuitBreakerState::HalfOpen => 0.5,
        CircuitBreakerState::Open => 1.0,
    };
    metrics().circuit_breaker_state.set(value);
}

/// Circuit breaker states
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum CircuitBreakerState {
    Closed,
    HalfOpen,
    Open,
}

// ============================================================================
// Tests
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_counter_increment() {
        let counter = Counter::new("test_counter", "Test counter");
        assert_eq!(counter.get(), 0);
        counter.inc();
        assert_eq!(counter.get(), 1);
        counter.inc_by(5);
        assert_eq!(counter.get(), 6);
    }

    #[test]
    fn test_gauge_operations() {
        let gauge = Gauge::new("test_gauge", "Test gauge");
        assert_eq!(gauge.get(), 0.0);
        gauge.set(42.5);
        assert_eq!(gauge.get(), 42.5);
        gauge.inc();
        assert_eq!(gauge.get(), 43.5);
        gauge.dec();
        assert_eq!(gauge.get(), 42.5);
    }

    #[test]
    fn test_histogram_observations() {
        let histogram = Histogram::new(
            "test_histogram",
            "Test histogram",
            vec![10.0, 50.0, 100.0]
        );

        histogram.observe(5.0);   // bucket 0
        histogram.observe(30.0);  // bucket 1
        histogram.observe(75.0);  // bucket 2
        histogram.observe(150.0); // +Inf bucket

        let output = histogram.to_openmetrics();
        assert!(output.contains("test_histogram_bucket"));
        assert!(output.contains("test_histogram_sum"));
        assert!(output.contains("test_histogram_count"));
    }

    #[test]
    fn test_command_success_rate() {
        let metrics = HubMetrics::new();

        // No commands yet
        assert_eq!(metrics.command_success_rate(), 1.0);

        // 3 successes, 1 failure = 75%
        metrics.command_success_count.inc_by(3);
        metrics.command_failure_count.inc();
        assert!((metrics.command_success_rate() - 0.75).abs() < 0.001);
    }

    #[test]
    fn test_openmetrics_export() {
        let metrics = HubMetrics::new();
        metrics.command_success_count.inc();
        metrics.wake_false_positive_count.inc_by(2);

        let output = metrics.export_openmetrics();

        assert!(output.contains("kagami_command_success_count 1"));
        assert!(output.contains("kagami_wake_false_positive_count 2"));
        assert!(output.contains("# EOF"));
    }

    #[test]
    fn test_counter_openmetrics_format() {
        let counter = Counter::new("my_counter", "My counter help");
        counter.inc();

        let output = counter.to_openmetrics();
        assert!(output.contains("# HELP my_counter My counter help"));
        assert!(output.contains("# TYPE my_counter counter"));
        assert!(output.contains("my_counter 1"));
    }
}

/*
 * Kagami Telemetry
 * Crystal (e7) - Verification through measurement
 *
 * What gets measured gets improved.
 * h(x) >= 0. Always.
 */
