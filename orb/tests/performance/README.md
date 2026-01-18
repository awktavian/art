# Performance Benchmarks

Comprehensive performance benchmarks to verify all performance claims with statistical rigor.

## Claims Verified

1. **Receipt → learning feedback <200ms** - `test_receipt_latency.py`
2. **~50 receipts/second throughput** - `test_throughput.py`
3. **<2% CPU overhead for background learning** - `test_cpu_overhead.py`
4. **64:1 compression ratio (E8)** - `test_compression_ratio.py`
5. **API P95 latency** - `test_api_latency.py`

## Quick Start

### Run All Benchmarks

```bash
# Full suite (recommended for CI/CD)
python scripts/benchmark/run_performance_suite.py --report

# Quick mode (faster, fewer iterations)
python scripts/benchmark/run_performance_suite.py --quick

# Generate HTML report
python scripts/benchmark/run_performance_suite.py --report --html benchmark_report.html
```

### Run Individual Benchmarks

```bash
# Receipt latency
pytest tests/performance/test_receipt_latency.py -v -s --benchmark-only

# Throughput
pytest tests/performance/test_throughput.py -v -s --benchmark-only

# CPU overhead
pytest tests/performance/test_cpu_overhead.py -v -s --benchmark-only

# E8 compression
pytest tests/performance/test_compression_ratio.py -v -s --benchmark-only

# API latency
pytest tests/performance/test_api_latency.py -v -s --benchmark-only
```

## Test Details

### 1. Receipt Latency (`test_receipt_latency.py`)

**Claim**: Receipt → learning feedback <200ms

**Tests**:
- `test_receipt_processing_latency_p95` - P95 latency with 95% CI
- `test_receipt_processing_latency_gpu` - GPU-timed latency (requires CUDA)
- `test_end_to_end_receipt_api_latency` - Full API → learning latency

**Success Criteria**: P95 latency < 200ms

**Methodology**:
- 100 iterations with warmup
- Statistical validation with 95% confidence intervals
- CUDA events for accurate GPU timing (when available)
- Wall clock timing as fallback

### 2. Throughput (`test_throughput.py`)

**Claim**: ~50 receipts/second throughput

**Tests**:
- `test_receipt_throughput_sustained` - Sustained throughput over 10 seconds
- `test_receipt_throughput_concurrent` - Concurrent processing throughput
- `test_receipt_batch_throughput` - Batch processing throughput
- `test_receipt_throughput_statistical_validation` - Multi-trial validation

**Success Criteria**: Mean throughput >= 50 receipts/sec (95% CI)

**Methodology**:
- 10-second sustained load test
- Multiple trials for statistical confidence
- Tests single-threaded, concurrent, and batch processing

### 3. CPU Overhead (`test_cpu_overhead.py`)

**Claim**: <2% CPU overhead for background learning

**Tests**:
- `test_background_learning_cpu_overhead` - Baseline vs learning CPU usage
- `test_memory_overhead` - Memory growth during learning
- `test_cpu_overhead_under_load` - CPU overhead at >50 receipts/sec
- `test_cpu_overhead_statistical_validation` - Multi-trial validation

**Success Criteria**: Mean CPU overhead < 2% (95% CI upper bound)

**Methodology**:
- Baseline CPU measurement (20 samples)
- Learning CPU measurement (50 samples)
- Statistical validation with 95% confidence intervals
- Uses `psutil` for accurate process-level CPU monitoring

### 4. E8 Compression (`test_compression_ratio.py`)

**Claim**: 64:1 compression ratio

**Tests**:
- `test_e8_compression_ratio` - Verify 64:1 ratio
- `test_e8_quantization_error` - Measure quantization error
- `test_e8_compression_throughput` - Compression speed
- `test_e8_compression_ratio_statistical_validation` - Multi-trial validation
- `test_e8_vs_naive_quantization` - Compare E8 vs naive quantization

**Success Criteria**: Compression ratio = 64:1 ± 0.1

**Methodology**:
- float32 (8 × 32 bits = 256 bits) → E8 lattice (4 bits/coord × 8 = 32 bits)
- Ratio: 256 / 32 = 64:1
- Perfect reconstruction verification (error < 1e-6)
- Demonstrates E8 superiority over naive quantization

### 5. API Latency (`test_api_latency.py`)

**Tests**:
- `test_api_health_endpoint_latency` - /health endpoint (<10ms P95)
- `test_api_intent_endpoint_latency` - /api/intents endpoint (<200ms P95)
- `test_api_receipts_list_latency` - /api/mind/receipts/ endpoint (<100ms P95)
- `test_api_concurrent_request_latency` - Latency under concurrent load
- `test_api_latency_statistical_validation` - Multi-endpoint validation
- `test_api_cold_start_vs_warm_latency` - Cold start overhead

**Success Criteria**: Endpoint-specific P95 thresholds

**Methodology**:
- Warmup phase to stabilize caches
- 50-100 requests per endpoint
- Statistical validation with 95% CI
- Concurrent load testing (1x, 5x, 10x, 20x)

## Statistical Validation

All benchmarks use proper statistical methods:

- **Warmup**: 10-20 iterations to stabilize caches, JIT compilation
- **Sample Size**: 50-100 iterations for statistical significance
- **Confidence Intervals**: 95% CI reported for all means
- **Percentiles**: P50, P95, P99 reported for latency tests
- **Multi-trial**: Critical tests run multiple trials

### Statistical Formulas

```python
# 95% Confidence Interval
stderr = std_dev / sqrt(n)
ci_95 = 1.96 * stderr
mean ± ci_95

# Percentiles
p95 = np.percentile(samples, 95)
```

## Continuous Monitoring

### Regression Detection

Run benchmarks in CI/CD and compare against baselines:

```bash
# Save baseline
python scripts/benchmark/run_performance_suite.py --json baseline.json

# Compare against baseline (in CI)
python scripts/benchmark/run_performance_suite.py --json current.json
python scripts/benchmark/compare_benchmarks.py baseline.json current.json
```

### Prometheus Metrics

Benchmarks emit metrics compatible with Prometheus:

- `kagami_benchmark_latency_ms{test="receipt_processing", quantile="0.95"}`
- `kagami_benchmark_throughput{test="receipt_processing"}`
- `kagami_benchmark_cpu_overhead_percent{test="background_learning"}`
- `kagami_benchmark_compression_ratio{test="e8_lattice"}`

## Requirements

```bash
# Core dependencies
pip install pytest pytest-benchmark pytest-asyncio

# System monitoring
pip install psutil

# Scientific computing
pip install numpy torch

# API testing
pip install fastapi httpx
```

## GPU Testing

Some tests use CUDA events for accurate GPU timing:

```bash
# GPU tests (requires CUDA)
pytest tests/performance/test_receipt_latency.py::test_receipt_processing_latency_gpu -v -s

# Skip GPU tests
pytest tests/performance/ -v -s --benchmark-only -m "not cuda"
```

## Output Format

### Console Output

```
======================================================================
RECEIPT PROCESSING LATENCY
======================================================================
Sample size:     100
Mean:            45.23ms ± 2.15ms (95% CI)
Std Dev:         10.82ms
P50 (median):    42.18ms
P95:             65.34ms
P99:             78.92ms
Min:             28.45ms
Max:             95.67ms
======================================================================
✓ PASS: P95 latency 65.34ms < 200ms
```

### JSON Output

```json
{
  "timestamp": "2025-01-15T10:30:00",
  "total_tests": 5,
  "passed": 5,
  "failed": 0,
  "results": [
    {
      "name": "Receipt Processing Latency",
      "claim": "Receipt → learning feedback <200ms",
      "threshold": 200.0,
      "measured": 65.34,
      "unit": "ms",
      "passed": true,
      "confidence_interval": 2.15
    }
  ]
}
```

### HTML Report

Includes:
- Summary table
- Detailed results per test
- System information
- Pass/fail status with color coding
- Timestamp and duration

## Troubleshooting

### Tests Fail Due to System Load

Run in isolated environment:

```bash
# Reduce system load
sudo renice -n -20 -p $$

# Run on dedicated hardware
taskset -c 0-3 pytest tests/performance/ --benchmark-only
```

### CUDA Not Available

GPU tests are skipped automatically if CUDA is unavailable. To run CPU-only:

```bash
pytest tests/performance/ -v -s --benchmark-only -m "not cuda"
```

### Memory Issues

Reduce batch sizes in tests or increase system memory.

## Contributing

When adding new performance benchmarks:

1. Follow existing test structure
2. Include warmup phase
3. Use proper statistical validation
4. Document success criteria
5. Add to `run_performance_suite.py`

## References

- [pytest-benchmark documentation](https://pytest-benchmark.readthedocs.io/)
- [E8 lattice (Viazovska 2017)](https://arxiv.org/abs/1603.04246)
- [Statistical validation methods](https://en.wikipedia.org/wiki/Confidence_interval)
