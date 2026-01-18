# Kagami Test Suite Architecture

## Overview

The Kagami test suite is designed for **100/100 quality** with comprehensive coverage across multiple testing dimensions. This document describes the architectural decisions, patterns, and best practices used throughout the test suite.

## Directory Structure

```
tests/
├── __init__.py              # Test suite metadata
├── conftest.py              # Root fixtures (auto-mocking, cleanup)
├── ARCHITECTURE.md          # This document
├── TEST_DEPENDENCIES.md     # Service dependency mapping
│
├── unit/                    # Tier 1: Pure unit tests (<1s)
│   ├── cognition/           # Cognitive system tests
│   ├── services/            # Service layer tests
│   └── ...
│
├── core/                    # Core component tests
│   ├── safety/              # Safety system tests
│   ├── world_model/         # World model tests
│   ├── memory/              # Memory system tests
│   └── ...
│
├── api/                     # API layer tests
│   ├── routes/              # Route handler tests
│   └── middleware/          # Middleware tests
│
├── integration/             # Tier 2: Integration tests (<5s)
│   └── ...                  # Cross-component tests
│
├── e2e/                     # Tier 3: End-to-end tests (10-60s)
│   └── ...                  # Full workflow tests
│
├── contracts/               # API contract tests
│   ├── test_api_response_contracts.py
│   ├── test_colony_api_contracts.py
│   ├── test_e8_protocol_contracts.py
│   └── test_receipt_protocol_contracts.py
│
├── property/                # Property-based tests (Hypothesis)
│   └── test_fano_properties.py
│
├── verification/            # Formal verification (Z3)
│   ├── test_cbf_adversarial.py
│   └── test_e8_optimality.py
│
├── safety/                  # Safety-specific tests
│   └── ...
│
├── chaos/                   # Chaos engineering
│   ├── test_connection_pool_exhaustion.py
│   ├── test_database_resilience.py
│   ├── test_network_partition.py
│   └── ...
│
├── performance/             # Performance & regression
│   ├── .benchmarks/         # Baseline data
│   └── test_regression.py
│
├── benchmarks/              # Benchmark tests
│   └── conftest.py          # Benchmark fixtures
│
├── load/                    # Load tests (100+ agents)
├── stress/                  # Stress tests
├── soak/                    # Long-running stability tests
│
├── fixtures/                # Shared fixtures
│   ├── mock_fixtures.py
│   └── mock_llm.py
│
└── utils/                   # Test utilities
    └── assertions.py
```

## Test Tiers

### Tier 1: Unit Tests
- **Location:** `tests/unit/`
- **Timeout:** <1s per test
- **Dependencies:** None
- **Run:** `make test-tier-1`

**Characteristics:**
- Pure functions, no I/O
- Mocked dependencies
- Fast feedback loop

### Tier 2: Integration Tests
- **Location:** `tests/integration/`, `tests/core/`, `tests/api/`
- **Timeout:** <5s per test
- **Dependencies:** Optional services
- **Run:** `make test-tier-2`

**Characteristics:**
- Cross-component integration
- May use real or mocked services
- Tests component interactions

### Tier 3: End-to-End Tests
- **Location:** `tests/e2e/`, `tests/contracts/`
- **Timeout:** 10-60s per test
- **Dependencies:** Full services
- **Run:** `make test-tier-3`

**Characteristics:**
- Full system workflows
- Real service interactions
- Production-like scenarios

## Testing Patterns

### 1. Property-Based Testing (Hypothesis)

```python
from hypothesis import given, strategies as st

@given(colony_pair=colony_pair_strategy())
@settings(max_examples=200)
def test_fano_anticommutativity(colony_pair):
    """Property: e_i × e_j = -(e_j × e_i)"""
    i, j = colony_pair
    result_ij = fano_multiply(i, j)
    result_ji = fano_multiply(j, i)
    assert result_ij == -result_ji
```

**Usage:**
- Mathematical properties (Fano plane, E8)
- Edge case discovery
- Invariant verification

### 2. Contract Testing (Syrupy)

```python
@pytest.mark.contract
def test_api_schema_stability(client, snapshot):
    """Contract: API schema must remain stable."""
    response = client.get("/api/status")
    normalized = normalize_response(response.json())
    assert normalized == snapshot
```

**Usage:**
- API backward compatibility
- Schema stability
- Protocol contracts

### 3. Formal Verification (Z3)

```python
from z3 import Real, Solver, sat

def test_cbf_non_negative():
    """Formal: h(x) >= 0 in safe set."""
    s = Solver()
    h = Real('h')
    s.add(h >= 0)  # Safety invariant
    assert s.check() == sat
```

**Usage:**
- Safety invariants
- Mathematical proofs
- Critical path verification

### 4. Chaos Engineering

```python
@pytest.mark.chaos
async def test_redis_mid_request_failure():
    """Chaos: System recovers from Redis failure mid-request."""
    async with simulate_failure("redis", after_ms=50):
        result = await process_request()
        assert result.status in ("success", "degraded")
```

**Usage:**
- Resilience testing
- Failure recovery
- Graceful degradation

### 5. Performance Regression

```python
def test_bench_e8_quantization(benchmark):
    """Benchmark: E8 quantization within 10% of baseline."""
    result = benchmark(nearest_e8, torch.randn(8))
    # CI compares against stored baseline
```

**Usage:**
- Latency tracking
- Throughput verification
- Regression detection

## Fixture Architecture

### Root Fixtures (`conftest.py`)

```python
@pytest.fixture(autouse=True)
def auto_mock_external_services(monkeypatch):
    """Auto-mock services unless KAGAMI_USE_REAL_SERVICES=1"""
    if os.getenv("KAGAMI_USE_REAL_SERVICES") != "1":
        # Install mocks
        ...

@pytest_asyncio.fixture(autouse=True)
async def reset_db_engine():
    """Reset in-memory SQLite per test."""
    yield
    await cleanup()
```

### Benchmark Fixtures (`benchmarks/conftest.py`)

```python
@pytest.fixture
def benchmark_with_warmup():
    """Benchmark fixture with warmup phase."""
    def run(func, *args, warmup=5, iterations=100):
        # Warmup
        for _ in range(warmup):
            func(*args)
        # Measure
        times = [timeit(func, *args) for _ in range(iterations)]
        return statistics(times)
    return run
```

### Mock Fixtures (`fixtures/mock_llm.py`)

```python
@pytest.fixture
def mock_llm():
    """Mock LLM for deterministic testing."""
    return MockLLM(responses={"test": "response"})
```

## Marker System

### Performance Tiers
- `@pytest.mark.tier_unit` - Tier 1 tests
- `@pytest.mark.tier_integration` - Tier 2 tests
- `@pytest.mark.tier_e2e` - Tier 3 tests

### Categories
- `@pytest.mark.contract` - Contract tests
- `@pytest.mark.property` - Property-based tests
- `@pytest.mark.chaos` - Chaos engineering
- `@pytest.mark.safety` - Safety tests
- `@pytest.mark.verification` - Formal verification
- `@pytest.mark.benchmark` - Performance benchmarks

### Infrastructure
- `@pytest.mark.requires_redis` - Needs Redis
- `@pytest.mark.requires_db` - Needs database
- `@pytest.mark.slow` - Long-running test

## Best Practices

### 1. Test Isolation
```python
# GOOD: Each test is independent
def test_create_user():
    user = create_user("test")
    assert user.id is not None

# BAD: Tests depend on each other
user_id = None
def test_create_user():
    global user_id
    user_id = create_user("test").id
def test_get_user():
    get_user(user_id)  # Depends on previous test
```

### 2. Descriptive Names
```python
# GOOD: Clear intent
def test_fano_routing_prefers_primary_colony_when_load_equal():
    ...

# BAD: Vague
def test_routing():
    ...
```

### 3. Arrange-Act-Assert
```python
def test_safety_check_blocks_unsafe_input():
    # Arrange
    filter = SafetyFilter()
    unsafe_input = "dangerous content"

    # Act
    result = filter.check(unsafe_input)

    # Assert
    assert not result.safe
    assert result.h_x < 0
```

### 4. Docstring Format
```python
def test_fano_anticommutativity(pair):
    """Property: e_i × e_j = -(e_j × e_i).

    Mathematical Claim: Fano multiplication is anticommutative.

    Verdict: PASS if signs flip when order reversed
    """
```

## CI Integration

### Standard CI (Every PR)
```yaml
# .github/workflows/ci.yml
jobs:
  test_unit:
    runs-on: ubuntu-latest
    steps:
      - run: pytest tests/unit/ -n auto
```

### Nightly CI (Extended Tests)
```yaml
# .github/workflows/nightly-stress.yml
jobs:
  adversarial:
    runs-on: ubuntu-latest
    timeout-minutes: 120
    steps:
      - run: pytest tests/verification/ --timeout=7200
```

### Performance Regression
```yaml
# .github/workflows/ci.yml
jobs:
  performance_regression:
    steps:
      - run: |
          pytest tests/performance/test_regression.py \
            --benchmark-compare-fail=mean:10%
```

## Quality Gates

| Metric | Threshold | Enforcement |
|--------|-----------|-------------|
| Coverage | ≥70% | CI fails below |
| Performance Regression | <10% | CI fails above |
| Contract Tests | All pass | CI fails on any |
| Safety Tests | All pass | CI fails on any |
| Mutation Score | ≥80% (safety) | Nightly check |

## Adding New Tests

### 1. Choose the Right Location
- Pure logic → `tests/unit/`
- Cross-component → `tests/integration/`
- Full workflow → `tests/e2e/`
- API stability → `tests/contracts/`

### 2. Add Appropriate Markers
```python
@pytest.mark.tier_unit
@pytest.mark.safety
def test_cbf_invariant():
    ...
```

### 3. Document Dependencies
If your test needs services, update `TEST_DEPENDENCIES.md`.

### 4. Consider Property Testing
For mathematical or algorithmic code, prefer Hypothesis.

### 5. Add Performance Budget
For critical paths, add to `baseline_budgets.json`.

## Debugging Failed Tests

### 1. Run Single Test
```bash
pytest tests/path/to/test.py::TestClass::test_method -v
```

### 2. Enable Debug Output
```bash
pytest tests/unit/ -v -s --tb=long
```

### 3. Run Without Parallelism
```bash
pytest tests/unit/ -n0
```

### 4. Check Service Dependencies
```bash
make services-health
```

### 5. Profile Slow Tests
```bash
make test-profile
```
