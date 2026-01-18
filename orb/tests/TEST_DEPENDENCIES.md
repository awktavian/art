# Test Dependencies & Service Requirements

This document maps test files to their external service dependencies and provides guidance on running tests in various environments.

## Quick Reference

| Test Directory | Redis | PostgreSQL | etcd | Weaviate | External APIs |
|---------------|-------|------------|------|----------|---------------|
| `tests/unit/` | - | - | - | - | - |
| `tests/core/` | Optional | Optional | - | - | - |
| `tests/api/` | Optional | Optional | - | - | - |
| `tests/integration/` | Required | Optional | Optional | Optional | - |
| `tests/e2e/` | Required | Required | Optional | Optional | - |
| `tests/chaos/` | Required | Required | Optional | - | - |
| `tests/contracts/` | - | - | - | - | Optional |
| `tests/safety/` | - | - | - | - | Optional (HF) |
| `tests/verification/` | - | - | - | - | - |

## Service Configuration

### Redis
```bash
# Docker
docker run -d --name redis -p 6379:6379 redis:7-alpine

# Environment variable
export REDIS_URL=redis://localhost:6379
```

**Required by:**
- `tests/integration/test_redis_*.py`
- `tests/chaos/test_redis_*.py`
- `tests/e2e/*`

### PostgreSQL / CockroachDB
```bash
# Docker (CockroachDB)
docker run -d --name cockroachdb -p 26257:26257 cockroachdb/cockroach start-single-node --insecure

# Environment variable
export DATABASE_URL=postgresql://root@localhost:26257/kagami?sslmode=disable
```

**Required by:**
- `tests/integration/test_storage_integration.py`
- `tests/e2e/*`

### etcd
```bash
# Docker
docker run -d --name etcd -p 2379:2379 quay.io/coreos/etcd:v3.5.0

# Environment variable
export ETCD_ENDPOINTS=localhost:2379
```

**Required by:**
- `tests/integration/test_config_*.py`

### Weaviate
```bash
# Docker
docker run -d --name weaviate -p 8085:8080 semitechnologies/weaviate:latest

# Environment variable
export WEAVIATE_URL=http://localhost:8085
```

**Required by:**
- `tests/integration/test_elysia_*.py`
- `tests/e2e/test_rag_*.py`

## Test Categories by Dependency Level

### Level 0: No External Dependencies
These tests run anywhere without any services:

```bash
pytest tests/unit/ tests/property/ tests/verification/
```

**Directories:**
- `tests/unit/` - Pure unit tests
- `tests/property/` - Hypothesis property-based tests
- `tests/verification/` - Z3 formal verification
- `tests/ablation/` - Ablation studies (some may need services)

### Level 1: Optional Redis
Tests that can run without Redis but benefit from it:

```bash
# Without Redis (uses mocks)
pytest tests/core/ tests/api/

# With Redis
KAGAMI_USE_REAL_SERVICES=1 pytest tests/core/ tests/api/
```

### Level 2: Required Services
Tests that need external services:

```bash
# Start services first
make services-start

# Run integration tests
pytest tests/integration/ tests/e2e/

# Stop services
make services-stop
```

### Level 3: External API Dependencies
Tests requiring external API keys:

```bash
# HuggingFace (for WildGuard safety model)
export HF_TOKEN=your_token
pytest tests/safety/test_wildguard_*.py

# Composio integration
export COMPOSIO_API_KEY=your_key
pytest tests/integration/test_composio_*.py
```

## Environment Variables

### Core Test Configuration
| Variable | Description | Default |
|----------|-------------|---------|
| `KAGAMI_USE_REAL_SERVICES` | Use real services instead of mocks | `0` |
| `KAGAMI_TEST_MODE` | Enable test mode optimizations | `1` |
| `KAGAMI_LOG_LEVEL` | Logging verbosity | `WARNING` |

### Service URLs
| Variable | Description | Default |
|----------|-------------|---------|
| `REDIS_URL` | Redis connection URL | `redis://localhost:6379` |
| `DATABASE_URL` | Database connection URL | SQLite in-memory |
| `ETCD_ENDPOINTS` | etcd cluster endpoints | `localhost:2379` |
| `WEAVIATE_URL` | Weaviate vector DB URL | `http://localhost:8085` |

### External APIs
| Variable | Description | Required For |
|----------|-------------|--------------|
| `HF_TOKEN` | HuggingFace API token | WildGuard tests |
| `OPENAI_API_KEY` | OpenAI API key | LLM integration tests |
| `COMPOSIO_API_KEY` | Composio API key | Tool integration tests |

## Running Tests by Environment

### Local Development
```bash
# Quick unit tests (no services)
make test-tier-1

# With local services
make services-start
make test-tier-2
make services-stop
```

### CI Environment
```bash
# GitHub Actions handles services automatically
# See .github/workflows/ci.yml for service configuration
```

### Docker-based Testing
```bash
# Start test infrastructure
docker-compose -f docker-compose.test.yml up -d

# Run tests
pytest tests/

# Cleanup
docker-compose -f docker-compose.test.yml down -v
```

## Test Fixtures That Manage Dependencies

### Auto-mocking Fixtures
The `conftest.py` provides fixtures that automatically mock services:

```python
@pytest.fixture(autouse=True)
def auto_mock_external_services(monkeypatch):
    """Mocks Redis, DB, etcd unless KAGAMI_USE_REAL_SERVICES=1"""
    if os.getenv("KAGAMI_USE_REAL_SERVICES") != "1":
        # Install mocks
        ...
```

### Service-aware Fixtures
```python
@pytest.fixture
def redis_client():
    """Returns real or mock Redis based on environment."""
    if os.getenv("KAGAMI_USE_REAL_SERVICES") == "1":
        return redis.from_url(os.getenv("REDIS_URL"))
    return MockRedis()
```

## Dependency Graph

```
                    ┌─────────────┐
                    │   unit/     │  No dependencies
                    └─────────────┘
                           │
                    ┌──────▼──────┐
                    │   core/     │  Optional: Redis
                    │   api/      │
                    └─────────────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
       ┌──────▼──────┐  ┌──▼───┐  ┌─────▼─────┐
       │ integration/│  │chaos/│  │contracts/ │
       └─────────────┘  └──────┘  └───────────┘
       Redis, DB, etcd   Redis,DB  Optional APIs
              │            │
              └────────────┼────────────┐
                           │            │
                    ┌──────▼──────┐     │
                    │    e2e/     │◄────┘
                    └─────────────┘
                    All services required
```

## Troubleshooting

### Redis Connection Errors
```bash
# Check if Redis is running
redis-cli ping  # Should return PONG

# Check URL format
echo $REDIS_URL  # Should be redis://localhost:6379
```

### Database Connection Errors
```bash
# For CockroachDB
cockroach sql --insecure -e "SELECT 1"

# Check connection string
echo $DATABASE_URL
```

### Tests Hanging
```bash
# Run with timeout
pytest tests/integration/ --timeout=60

# Run serially for debugging
pytest tests/integration/ -n0 -v
```

### Fixture Scope Issues
If tests fail with "event loop is closed", ensure async fixtures use function scope:
```python
@pytest_asyncio.fixture(scope="function")
async def async_fixture():
    ...
```
