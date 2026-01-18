# Performance Optimization Guide

Kagami Hub is designed for low-latency voice interactions on resource-constrained
hardware (Raspberry Pi 4). This document describes the key optimizations.

## Latency Targets

| Operation | Target | Measured |
|-----------|--------|----------|
| Wake word detection | < 50ms | ~30ms |
| STT (local Whisper) | < 2s | ~1.5s (tiny.en) |
| TTS (local Piper) | < 500ms | ~300ms |
| Command parsing | < 10ms | ~2ms |
| End-to-end response | < 3s | ~2.5s |

## Key Optimizations

### 1. Audio Processing

#### Continuous Ring Buffer
```rust
// Audio captured continuously into fixed-size ring buffer
// Only copies data when speech detected (VAD)
pub struct AudioRingBuffer {
    buffer: VecDeque<f32>,
    capacity: usize,
}
```

**Benefit**: No allocation during audio capture, O(1) append and read.

#### Voice Activity Detection
- RMS-based energy detection
- Configurable silence/speech frame counts
- Prevents processing silence

### 2. Speech-to-Text

#### Model Selection
- **Whisper tiny.en** (75MB): Fastest, English-only
- Cloud fallback for accuracy-critical queries

#### Async Inference
```rust
// CPU-intensive inference runs on blocking threadpool
tokio::task::spawn_blocking(move || {
    whisper.transcribe(&audio)
}).await
```

**Benefit**: Main async runtime never blocked.

### 3. Text-to-Speech

#### Phrase Caching
```rust
// Common phrases pre-synthesized and cached
pub struct TTSEngine {
    cache: RwLock<HashMap<String, Vec<f32>>>,
}
```

Cached phrases:
- "Okay"
- "I've turned on the lights"
- "Goodnight"
- Common confirmations

**Benefit**: Instant response for common phrases.

#### Resampling Optimization
- Piper outputs 22050Hz
- System needs 16000Hz or 48000Hz
- Single-pass linear resampling

### 4. Command Processing

#### Pattern Matching First
- Simple regex for common commands
- LLM only for complex/ambiguous queries

```rust
// Fast path
if text.contains("lights") && text.contains("on") {
    return Command::LightsOn { rooms };
}
// Slow path
llm.interpret(text).await
```

### 5. Mesh Networking

#### CRDT State Sync
- Vector clocks for causality
- Only sync deltas, not full state
- No locking conflicts

#### mDNS Caching
- Peer discovery results cached
- Refresh every 30 seconds

### 6. Memory Management

#### Pre-allocation
- Audio buffers allocated at startup
- Model memory mapped once

#### Avoiding Allocations in Hot Paths
```rust
// Bad: Allocates on every call
fn process(audio: &[f32]) -> Vec<f32> {
    audio.iter().map(|x| x * 2.0).collect()
}

// Good: Reuse buffer
fn process_into(audio: &[f32], output: &mut [f32]) {
    for (i, x) in audio.iter().enumerate() {
        output[i] = x * 2.0;
    }
}
```

### 7. Async Best Practices

#### spawn_blocking for CPU Work
- Whisper inference
- Vosk processing
- Audio encoding

#### Proper Channel Sizing
```rust
// Bounded channels prevent memory growth
let (tx, rx) = tokio::sync::mpsc::channel(100);
```

## Profiling

### CPU Profiling
```bash
# perf on Linux
perf record -g ./kagami-hub
perf report

# Instruments on macOS
xcrun xctrace record --template 'Time Profiler' --launch ./kagami-hub
```

### Memory Profiling
```bash
# Valgrind
valgrind --tool=massif ./kagami-hub
ms_print massif.out.*

# heaptrack
heaptrack ./kagami-hub
heaptrack_gui heaptrack.kagami-hub.*
```

### Latency Measurement
```rust
let start = std::time::Instant::now();
// ... operation ...
tracing::info!(
    latency_ms = start.elapsed().as_millis(),
    "operation complete"
);
```

## Resource Limits

### Raspberry Pi 4 (4GB)
- Target memory: < 500MB
- Target CPU: < 50% sustained
- Peak CPU during inference: acceptable

### Thread Pool Sizing
```rust
// CPU-bound work: num_cpus
// IO-bound work: larger pool
tokio::runtime::Builder::new_multi_thread()
    .worker_threads(4)  // Pi 4 has 4 cores
    .max_blocking_threads(8)
    .build()
```

## Benchmarks

Run benchmarks with:
```bash
cargo bench
```

Key benchmarks:
- `bench_vad_process`: VAD throughput
- `bench_command_parse`: Parser speed
- `bench_audio_resample`: Resampling throughput

## Optimization Checklist

Before release, verify:

- [ ] No allocations in audio callback
- [ ] STT runs on blocking pool
- [ ] Common phrases cached
- [ ] WebSocket messages bounded
- [ ] Proper backpressure on channels
- [ ] Memory stable under load test
- [ ] Latency within targets

## Known Bottlenecks

| Bottleneck | Impact | Mitigation |
|------------|--------|------------|
| Whisper inference | ~1.5s | Use tiny model, cloud fallback |
| Piper first synthesis | ~300ms | Pre-warm, caching |
| mDNS discovery | ~2s initial | Background, cached |
| TLS handshake | ~200ms | Connection pooling |

---

*鏡 — Fast enough to feel magical. Slow enough to be safe.*

*h(x) ≥ 0. Always.*
