# Performance Benchmarks - Quick Start Guide

## TL;DR

```bash
# Run all benchmarks
python scripts/benchmark/run_performance_suite.py --report

# Quick mode (faster)
python scripts/benchmark/run_performance_suite.py --quick

# Individual test
pytest tests/performance/test_receipt_latency.py -v -s --benchmark-only
```

## What Gets Tested

| Claim | File | Command |
|-------|------|---------|
| Receipt → learning <200ms | test_receipt_latency.py | `pytest tests/performance/test_receipt_latency.py -v -s --benchmark-only` |
| ~50 receipts/sec | test_throughput.py | `pytest tests/performance/test_throughput.py -v -s --benchmark-only` |
| <2% CPU overhead | test_cpu_overhead.py | `pytest tests/performance/test_cpu_overhead.py -v -s --benchmark-only` |
| 64:1 compression | test_compression_ratio.py | `pytest tests/performance/test_compression_ratio.py -v -s --benchmark-only` |

## Reading Results

### PASS Example
```
✓ PASS: P95 latency 65.34ms < 200ms
```
Claim verified!

### FAIL Example
```
✗ FAIL: P95 latency 250.45ms >= 200ms
```
Performance regression detected.

## Test Structure

Each test includes:
- **Warmup**: 10-20 iterations to stabilize
- **Measurement**: 50-100 iterations
- **Statistics**: Mean, P50, P95, P99, 95% CI
- **Success Criteria**: Threshold validation

## Quick Commands

```bash
# All benchmarks with report
python scripts/benchmark/run_performance_suite.py --report

# Save JSON results
python scripts/benchmark/run_performance_suite.py --json results.json

# Generate HTML report
python scripts/benchmark/run_performance_suite.py --html report.html

# Quick mode (fewer iterations)
python scripts/benchmark/run_performance_suite.py --quick

# Single test
pytest tests/performance/test_receipt_latency.py::test_receipt_processing_latency_p95 -v -s

# All receipt tests
pytest tests/performance/test_receipt_latency.py -v -s --benchmark-only

# Skip GPU tests
pytest tests/performance/ -v -s --benchmark-only -m "not cuda"
```

## Interpreting Output

### Latency Tests
```
P95: 65.34ms < 200ms ✓
```
- **P95**: 95% of requests complete in this time
- **Target**: <200ms
- **Status**: Pass if P95 < threshold

### Throughput Tests
```
Throughput: 55.23 receipts/sec >= 50 receipts/sec ✓
```
- **Measured**: 55.23 receipts/sec
- **Target**: >= 50 receipts/sec
- **Status**: Pass if mean >= threshold

### CPU Overhead Tests
```
CPU overhead: 1.8% < 2% ✓
```
- **Measured**: 1.8% CPU increase
- **Target**: <2%
- **Status**: Pass if overhead < threshold

### Compression Tests
```
Compression ratio: 64.0:1 = 64:1 ✓
```
- **Measured**: 64.0:1
- **Target**: 64:1 (exactly)
- **Status**: Pass if ratio matches

## Troubleshooting

### High Latency
- Check system load
- Close other applications
- Run on isolated hardware

### Low Throughput
- Check CPU throttling
- Verify GPU availability (if needed)
- Check memory pressure

### High CPU Overhead
- Verify no other processes running
- Check background tasks
- Validate process isolation

### Tests Timeout
- Increase timeout: `pytest --timeout=600`
- Run in quick mode: `--quick`

## Dependencies

All dependencies already in requirements:
- pytest
- pytest-benchmark
- pytest-asyncio
- numpy
- torch
- psutil
- fastapi
- httpx

## Common Issues

**Issue**: CUDA not available
**Solution**: GPU tests skipped automatically, use CPU tests

**Issue**: Memory error
**Solution**: Reduce batch sizes in tests

**Issue**: Tests fail under load
**Solution**: Run in isolated environment

## Full Documentation

- README.md - Complete documentation
- BENCHMARK_SUMMARY.md - Implementation details
- PERFORMANCE_BENCHMARKS_REPORT.md - Full report

## Questions?

See tests/performance/README.md for detailed documentation.
