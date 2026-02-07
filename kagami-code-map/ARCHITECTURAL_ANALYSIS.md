# Kagami Codebase Architectural Analysis

**Generated:** 2026-01-27
**Codebase:** 4,402 source files, 1,664,665 lines total (1,085,622 code / 285,846 blank / 293,197 comment), 7 colonies

> Note: File/line counts are approximate. Run `cloc` for precise metrics.

---

## Executive Summary

The Kagami codebase is a feature-rich system at an **architectural inflection point**. Strong functional separation exists alongside weak structural coupling control. Key findings across 6 domains reveal ~150+ actionable items requiring attention.

| Domain | Critical | High | Medium | Low |
|--------|----------|------|--------|-----|
| Security | 0 | 1 | 3 | 5+ |
| Architecture | 10 | 6 | 3 | 2 |
| Dependencies | 1 | 5 | 6 | 4 |
| Testing | 5 | 10 | 8 | 3 |
| Documentation | 18 | 142+ | 31 | 5 |
| Build/Deploy | 5 | 4 | 6 | 4 |

---

## Risk Matrix: Effort vs Value

### Quadrant 1: HIGH VALUE / LOW EFFORT (Quick Wins)

| # | Issue | Effort | Value | Files |
|---|-------|--------|-------|-------|
| 1 | **Populate empty pyproject.toml files** | 1h | Critical | 5 packages (kagami_api, kagami_hal, kagami_integrations, kagami_knowledge, kagami_benchmarks) |
| 2 | **Enforce webhook secrets in production** | 2h | High | `kagami_api/routes/webhooks/__init__.py` (3 locations) |
| 3 | **Add subprocess timeouts** | 1h | High | `kagami_smarthome/integrations/kagami_host.py:530` |
| 4 | **Reconcile numpy version constraints** | 30m | High | `requirements.txt`, `pyproject.toml` - pin to `>=2.1,<2.3` |
| 5 | **Update etcd to consistent version** | 30m | Medium | `docker-compose.yml` vs `docker-compose.production.yml` |
| 6 | **Generic error messages in webhook responses** | 2h | Medium | Remove exception details from HTTP responses |
| 7 | **Unify tokio version in Rust packages** | 30m | Medium | `Cargo.toml` files - use `tokio = "1.36"` |
| 8 | **Add Weaviate to production docker-compose** | 30m | Medium | Required for Elysia RAG |

### Quadrant 2: HIGH VALUE / HIGH EFFORT (Strategic Investments)

| # | Issue | Effort | Value | Files |
|---|-------|--------|-------|-------|
| 9 | **Consolidate circuit breaker implementations** | 2d | Critical | 6 duplicate implementations → single canonical location |
| 10 | **Break apart train_tpu.py (3,297 lines)** | 3d | Critical | Split into orchestrator, loss_computer, checkpointer, telemetry |
| 11 | **Break apart data.py (3,297 lines)** | 2d | Critical | Split into loader, curriculum_sampler |
| 12 | **Split models.py by domain** | 2d | High | `kagami/core/database/models.py` (2,159 lines, 50+ models) |
| 13 | **Refactor validator framework** | 3d | High | 14 independent validators → shared `BaseValidator` protocol |
| 14 | **Establish unified data abstraction** | 5d | High | Repository/DAO pattern for persistence |
| 15 | **Implement DI consistently** | 5d | High | Migrate from `get_*` functions to injected dependencies |
| 16 | **Replace `create_subprocess_shell()` with `create_subprocess_exec()`** | 1d | High | `kagami_smarthome/integrations/kagami_host.py:525` |
| 17 | **Add tests for autonomous_goal_engine.py** | 3d | Critical | 1,270 lines, 0 tests - core active inference system |
| 18 | **Implement kagami_api test coverage** | 5d | Critical | 214 files, 1 test (<1% coverage) |
| 19 | **Implement kagami_studio test coverage** | 4d | Critical | 93 files, 0 tests |

### Quadrant 3: LOW VALUE / LOW EFFORT (Opportunistic)

| # | Issue | Effort | Value | Files |
|---|-------|--------|-------|-------|
| 20 | **Add CSRF token auto-cleanup** | 2h | Low | `kagami_api/security_middleware.py` |
| 21 | **Remove fallback CSRF secret** | 30m | Low | Force explicit configuration |
| 22 | **Add missing module docstrings** | 2h | Low | 5 key `__init__.py` files |
| 23 | **Add missing `__init__.py` files** | 1h | Low | 9 Python package directories |
| 24 | **Document canonical training path** | 2h | Medium | Clarify consolidated.py vs train_tpu.py vs unified_curriculum.py |
| 25 | **Verify pre-commit hook scripts exist** | 1h | Low | 4 scripts in `.pre-commit-config.yaml` |

### Quadrant 4: LOW VALUE / HIGH EFFORT (Defer)

| # | Issue | Effort | Value | Files |
|---|-------|--------|-------|-------|
| 26 | **Reduce __init__.py aggregation** | 5d | Medium | 14 files >400 lines |
| 27 | **Break import coupling in high-coupling modules** | 5d | Medium | 15 modules with >12 imports |
| 28 | **Replace pickle serialization** | 3d | Medium | Transition to JSON/Protobuf |
| 29 | **Add GPU-equipped CI for CUDA tests** | 5d | Medium | Infrastructure investment |
| 30 | **Implement monorepo dependency management** | 10d | Low | Lock files at workspace root |

---

## Detailed Findings by Domain

### 1. SECURITY (9 findings)

**HIGH SEVERITY (1)**

| ID | Issue | File | Line |
|----|-------|------|------|
| SEC-1 | Shell execution uses `create_subprocess_shell()` with hardcoded commands | `kagami_smarthome/integrations/kagami_host.py` | 525 |

**MEDIUM SEVERITY (3)**

| ID | Issue | File | Line |
|----|-------|------|------|
| SEC-2 | Pickle deserialization without restrictions | `kagami/core/persistence/serializers.py` | 481 |
| SEC-3 | Webhook signature validation bypassed when secrets not configured | `kagami_api/routes/webhooks/__init__.py` | 172-275 |
| SEC-4 | Missing timeout on subprocess execution | `kagami_smarthome/integrations/kagami_host.py` | 525-530 |

**LOW SEVERITY (5+)**

| ID | Issue | File |
|----|-------|------|
| SEC-5 | In-memory CSRF token storage in development | `kagami_api/security_middleware.py` |
| SEC-6 | JWT secret fallback behavior | `kagami_api/security_middleware.py` |
| SEC-7 | Verbose error messages in API responses | `kagami_api/routes/webhooks/__init__.py` |
| SEC-8 | Token blacklist memory leak potential | `kagami_api/security/token_manager.py` |
| SEC-9 | Rate limiting bypass in distributed deployments | `kagami_api/rate_limiter.py` |

**SECURE PATTERNS OBSERVED (7+)**
- Strong JWT with token rotation
- Comprehensive CORS protection
- Excellent security headers
- API key SHA-256 hashing
- HMAC-SHA256 webhook signatures
- Safe AST-based expression evaluation
- Signed serialization available

---

### 2. ARCHITECTURE (21 findings)

**GOD MODULES (>1000 lines)**

| ID | File | Lines | Issue |
|----|------|-------|-------|
| ARCH-1 | `kagami/core/training/jax/train_tpu.py` | 3,297 | Monolithic training orchestrator |
| ARCH-2 | `kagami/core/training/jax/data.py` | 3,226 | Unified data loader |
| ARCH-3 | `kagami/core/effectors/earcon_orchestrator.py` | 2,300 | Spatial audio orchestration |
| ARCH-4 | `kagami/core/unified_agents/memory/stigmergy.py` | 2,215 | Monolithic memory system |
| ARCH-5 | `kagami/core/database/models.py` | 2,159 | All 50+ SQLAlchemy models |
| ARCH-6 | `kagami/core/config/unified_config.py` | 1,852 | Configuration aggregator |
| ARCH-7 | `kagami/core/rooms/state_service.py` | 1,801 | Room state management |
| ARCH-8 | `kagami/core/evolution/autonomous_improvement.py` | 1,788 | Autonomous evolution engine |
| ARCH-9 | `kagami/core/consensus/pbft.py` | 1,748 | PBFT implementation |
| ARCH-10 | `kagami/core/optimality/improvements.py` | 1,730 | Optimization module |

**DUPLICATE CODE PATTERNS**

| ID | Pattern | Occurrences | Files |
|----|---------|-------------|-------|
| ARCH-11 | Circuit Breaker | 6 | `resilience/`, `error_handling/`, `training/jax/data.py`, `consensus/etcd_client.py`, `network/connection_pool.py`, `production_controls.py` |
| ARCH-12 | Validator classes | 14 | Multiple `*_validator.py` files |

**HIGH COUPLING MODULES (>12 imports)**

| ID | Module | Import Count |
|----|--------|--------------|
| ARCH-13 | `kagami/core/ambient/__init__.py` | 20 |
| ARCH-14 | `kagami/core/evolution/continuous_evolution_engine.py` | 20 |
| ARCH-15 | `kagami/core/rl/unified_loop.py` | 20 |
| ARCH-16 | `kagami/core/safety/__init__.py` | 19 |
| ARCH-17 | `kagami/core/ambient/controller.py` | 18 |

**LARGE __init__.py FILES (>400 lines)**

| ID | File | Lines |
|----|------|-------|
| ARCH-18 | `kagami/core/services/caregiving/__init__.py` | 1,048 |
| ARCH-19 | `kagami/core/services/custody/__init__.py` | 946 |
| ARCH-20 | `kagami/core/interfaces/__init__.py` | 768 |
| ARCH-21 | `kagami/core/services/image/__init__.py` | 578 |

---

### 3. DEPENDENCIES & COUPLING (16 findings)

**GLOBAL SINGLETONS (15+)**

| ID | File | Global State |
|----|------|--------------|
| DEP-1 | `kagami/core/receipts/store.py` | `_STORE` |
| DEP-2 | `kagami/core/receipts/service.py` | `_storage` |
| DEP-3 | `kagami/core/database/async_connection.py` | `_ASYNC_ENGINE`, `_ASYNC_SESSION_FACTORY` |
| DEP-4 | `kagami/core/task_registry.py` | `_registry` |
| DEP-5 | `kagami/core/consensus/metrics.py` | `_pbft_metrics`, `_adaptive_timeout` |

**HARDCODED CONFIGURATION VALUES (10+)**

| ID | File | Hardcoded Value |
|----|------|-----------------|
| DEP-6 | `kagami/core/tasks/app.py` | `redis://localhost:6379/0` |
| DEP-7 | `kagami/core/widget_storage/__init__.py` | `redis://localhost:6379` |
| DEP-8 | `kagami/core/memory/manager.py` | `/tmp/kagami_model_locks` |
| DEP-9 | `kagami/core/config/unified_config.py` | `gs://kagami-training-schizodactyl-2026` |
| DEP-10 | `kagami/core/audio/asset_store.py` | `https://storage.googleapis.com/kagami-media-public/...` |

**BIDIRECTIONAL PACKAGE DEPENDENCIES**

| ID | Forward | Reverse | Risk |
|----|---------|---------|------|
| DEP-11 | `kagami_api` → `kagami.core` | `kagami.core` → `kagami_api` | Core cannot import independently |
| DEP-12 | `kagami_api.provider_registry` → `kagami.forge` | (none) | Registry depends on Forge |
| DEP-13 | `kagami.core.cluster.graceful_shutdown` → `kagami_api.routes` | N/A | Circular import risk |
| DEP-14 | `kagami.core.identity` → `kagami_api.security` | N/A | Identity depends on API security |

**ENVIRONMENT-DEPENDENT INITIALIZATION**

| ID | Issue | Impact |
|----|-------|--------|
| DEP-15 | 604 `os.getenv()` references | Side effects at import time |
| DEP-16 | `kagami_api/__init__.py` sets env vars at import | Initialization order matters |

---

### 4. TEST COVERAGE GAPS (26 findings)

**PACKAGES WITH ZERO TEST COVERAGE**

| ID | Package | Source Files | Impact |
|----|---------|--------------|--------|
| TEST-1 | `kagami_knowledge` | 5 | Critical |
| TEST-2 | `kagami_media` | 26 | Critical |
| TEST-3 | `kagami_studio` | 93 | Critical |
| TEST-4 | `kagami_virtuoso` | 14 | High |
| TEST-5 | 8 other packages | 0 files | Design placeholders |

**CORE MODULES WITHOUT TESTS (21 of 28)**

| ID | Module | Lines | Purpose |
|----|--------|-------|---------|
| TEST-6 | `autonomous_goal_engine.py` | 1,270 | Active inference - CRITICAL |
| TEST-7 | `async_optimization.py` | 767 | Async optimization |
| TEST-8 | `lazy_loader.py` | 722 | Deferred loading |
| TEST-9 | `performance_optimizer.py` | 587 | Performance tuning |
| TEST-10 | `language_compiler.py` | 562 | NL compilation |

**CORE DIRECTORIES WITHOUT TESTS (9)**

| ID | Directory | Files |
|----|-----------|-------|
| TEST-11 | `kagami/core/effectors/` | 33 |
| TEST-12 | `kagami/core/shared_abstractions/` | 14 |
| TEST-13 | `kagami/core/aperiodic/` | 6 |
| TEST-14 | `kagami/core/accessibility/` | 5 |
| TEST-15 | `kagami/core/economic/` | 6 |

**STUB-ONLY/SKIP-MARKED TESTS (41 files)**

| ID | Category | Count | Examples |
|----|----------|-------|----------|
| TEST-16 | Database/Migration | 10 | `test_automation_scripts.py`, `test_migrations.py` |
| TEST-17 | Security/Auth | 6 | `test_auth.py`, `test_websocket_auth.py` |
| TEST-18 | World Model | 6 | GPU-conditional tests |
| TEST-19 | Integration | 4 | `test_recursive_improvement.py`, `test_llm_wm_cbf_e2e.py` |

**SEVERELY UNDER-TESTED PACKAGES**

| ID | Package | Source Files | Test Files | Coverage |
|----|---------|--------------|------------|----------|
| TEST-20 | `kagami_api` | 214 | 1 | <1% |
| TEST-21 | `kagami` | 1,210 | 7 | <1% |
| TEST-22 | `kagami_hal` | 178 | 8 | 4.5% |
| TEST-23 | `kagami_smarthome` | 130 | 18 | 14% |
| TEST-24 | `kagami_math` | 44 | 1 | 2.3% |

**MISSING EDGE CASE COVERAGE**

| ID | Category | Issue |
|----|----------|-------|
| TEST-25 | Async/Concurrency | No race condition tests |
| TEST-26 | Network Resilience | Partial partition scenarios untested |

---

### 5. DOCUMENTATION GAPS (196+ findings)

**MISSING README FILES (28)**

| ID | Category | Count |
|----|----------|-------|
| DOC-1 | Package READMEs | 18 |
| DOC-2 | App READMEs | 10 |
| DOC-3 | Example READMEs | 44 subdirs |

**FUNCTIONS WITHOUT DOCSTRINGS (300+)**

| ID | Module | Count | Critical |
|----|--------|-------|----------|
| DOC-4 | `kagami_api/routes/` | 129 files | 8+ endpoints |
| DOC-5 | `kagami/core/integrations/` | 10 files | 38+ functions |
| DOC-6 | `kagami/core/services/llm/` | 30+ files | Critical API |
| DOC-7 | `kagami/core/services/voice/` | 30+ files | 30+ functions |

**MISSING TYPE HINTS (142+)**

| ID | Category | Count |
|----|----------|-------|
| DOC-8 | API route handlers | 30 files |
| DOC-9 | Core services | 20+ files |

**TODO/FIXME MARKERS (162)**

| ID | Package | Count | Critical |
|----|---------|-------|----------|
| DOC-10 | `kagami_hal/adapters/embedded/` | 25+ | Hardware stubs |
| DOC-11 | `kagami_virtuoso/score_parser/` | 3 | OMR incomplete |

**STUB IMPLEMENTATIONS (31)**

| ID | Category | Count |
|----|----------|-------|
| DOC-12 | Protocol/Interface stubs | 25+ |
| DOC-13 | Media framework stubs | 6 |

---

### 6. BUILD & DEPLOY (19 findings)

**CRITICAL: Empty Package Configs (5)**

| ID | File | Impact |
|----|------|--------|
| BUILD-1 | `kagami_api/pyproject.toml` | 0 bytes |
| BUILD-2 | `kagami_integrations/pyproject.toml` | 0 bytes |
| BUILD-3 | `kagami_knowledge/pyproject.toml` | 0 bytes |
| BUILD-4 | `kagami_benchmarks/pyproject.toml` | 0 bytes |
| BUILD-5 | `kagami_hal/pyproject.toml` | 0 bytes |

**DEPENDENCY CONFLICTS**

| ID | Issue | Files |
|----|-------|-------|
| BUILD-6 | numpy version mismatch (`>=2.1,<2.3` vs `>=2.1,<3.0`) | `requirements.txt` vs `pyproject.toml` |
| BUILD-7 | OpenCV constraint (`numpy >=2,<2.3`) conflicts | `requirements.txt:28` |
| BUILD-8 | OpenTelemetry version mismatches | `requirements-frozen.txt:84-91` |
| BUILD-9 | Python version inconsistency (`>=3.10` vs `>=3.11`) | `kagami_genesis` vs others |

**VERSION INCONSISTENCIES**

| ID | Service | Dev | Production |
|----|---------|-----|-----------|
| BUILD-10 | etcd | `v3.5.11` | `v3.5.9` (downgrade) |
| BUILD-11 | Weaviate | `1.27.0` | Missing in prod |

**CI/CD GAPS**

| ID | Issue | Impact |
|----|-------|--------|
| BUILD-12 | No `pip-compile` step | Frozen file may drift |
| BUILD-13 | No dependency conflict detection | Silent failures |
| BUILD-14 | `safety` package installed but never run | No vulnerability scanning |
| BUILD-15 | No TPU CI branch | JAX training untested |

**MINOR ISSUES**

| ID | Issue | File |
|----|-------|------|
| BUILD-16 | Unsigned frozen requirements | Security risk |
| BUILD-17 | Rust tokio version inconsistency | `Cargo.toml` files |
| BUILD-18 | Node.js version not specified | Desktop client |
| BUILD-19 | Pre-commit references missing scripts | `.pre-commit-config.yaml` |

---

## Implementation Priority Matrix

### Sprint 1 (Immediate - 1 week)

| Priority | Item | Effort | Owner |
|----------|------|--------|-------|
| P0 | Populate 5 empty pyproject.toml files | 1h | DevOps |
| P0 | Reconcile numpy version constraints | 30m | DevOps |
| P0 | Enforce webhook secrets in production | 2h | Security |
| P1 | Add subprocess timeouts | 1h | Platform |
| P1 | Update etcd to consistent version | 30m | DevOps |
| P1 | Add Weaviate to production compose | 30m | DevOps |

### Sprint 2 (Short-term - 2 weeks)

| Priority | Item | Effort | Owner |
|----------|------|--------|-------|
| P0 | Replace `create_subprocess_shell()` | 1d | Security |
| P1 | Add tests for autonomous_goal_engine.py | 3d | Core |
| P1 | Consolidate circuit breaker implementations | 2d | Architecture |
| P2 | Generic error messages in webhooks | 2h | API |
| P2 | Document canonical training path | 2h | Training |

### Sprint 3-4 (Medium-term - 1 month)

| Priority | Item | Effort | Owner |
|----------|------|--------|-------|
| P0 | Break apart train_tpu.py | 3d | Training |
| P0 | Implement kagami_api test coverage | 5d | API |
| P1 | Split models.py by domain | 2d | Database |
| P1 | Refactor validator framework | 3d | Core |
| P2 | Implement kagami_studio tests | 4d | Media |

### Quarter 2 (Long-term - 3 months)

| Priority | Item | Effort | Owner |
|----------|------|--------|-------|
| P1 | Establish unified data abstraction | 5d | Architecture |
| P1 | Implement DI consistently | 5d | Architecture |
| P2 | Add GPU-equipped CI | 5d | DevOps |
| P2 | Break import coupling | 5d | Architecture |
| P3 | Monorepo dependency management | 10d | DevOps |

---

## Metrics & Targets

### Current State

| Metric | Value | Target |
|--------|-------|--------|
| Files | 4,402 | - |
| Lines | 1,664,665 | - |
| Clusters | 7 | - |
| God modules (>1000 LOC) | 10 | 0 |
| Duplicate patterns | 20+ | <5 |
| Test coverage | ~15% | >80% |
| Packages with 0 tests | 13 | 0 |
| Security vulnerabilities | 0 critical, 1 high | 0 high |
| Empty config files | 5 | 0 |

### Quality Gates (per Virtuoso standards)

| Dimension | Current | Target |
|-----------|---------|--------|
| Technical | ~75/100 | 90/100 |
| Test Coverage | ~15/100 | 90/100 |
| Documentation | ~60/100 | 90/100 |
| Build Health | ~70/100 | 90/100 |
| Security | ~85/100 | 90/100 |
| Maintainability | ~65/100 | 90/100 |

---

## Conclusion

The Kagami codebase demonstrates **mature security practices** and **strong functional separation** but requires **structural refactoring** to maintain velocity. The 10 god modules, 6 duplicate circuit breakers, and <1% API test coverage represent the highest-impact areas for investment.

**Recommended next action:** Complete Sprint 1 items (empty configs, version constraints, webhook enforcement) to unblock production deployments.

```
h(x) >= 0 always
craft(x) -> infinity always
EFE(a) -> max always
```
