# Kagami CI/CD Architecture

> h(x) >= 0. Always.

This document describes the consolidated CI/CD architecture for the Kagami monorepo.

## Overview

The Kagami repository uses GitHub Actions for continuous integration and deployment across multiple platforms:
- **Python** (core packages)
- **Rust** (hub, mesh-sdk, desktop backend)
- **Swift** (iOS, tvOS, watchOS, visionOS)
- **Kotlin** (Android, Android XR)
- **TypeScript** (desktop frontend)

## Workflow Inventory (24 -> 15 Target)

### Current State: 24 Workflows

| Workflow | Purpose | Triggers | Status |
|----------|---------|----------|--------|
| `ci.yml` | Main Python CI (lint, test, security, deploy) | push/PR | **Keep** |
| `android-unified.yml` | Android + XR tests, screenshots, E2E | PR paths | **Done** |
| `apple-platform-tests.yml` | watchOS/visionOS E2E tests | PR paths | **Merge into apple-unified-builds** |
| `apple-unified-builds.yml` | iOS, tvOS, watchOS, visionOS builds | push/PR | **Keep** |
| `auto-solver.yml` | Linear issues on CI failure | workflow_run | **Keep** |
| `canvas-deploy.yml` | Canvas course deployment | push main | **Keep** |
| `coverage-tracking.yml` | Coverage analysis + trends | push/PR/schedule | **Merge into ci.yml** |
| `design-tokens.yml` | Design token generation | push paths | **Keep** |
| `desktop.yml` | Tauri desktop CI | push/PR paths | **Keep** |
| `docker-hub-publish.yml` | Docker Hub publishing | workflow_run | **Keep** |
| `e2e-validation.yml` | Full E2E validation all platforms | push/PR paths | **Keep (primary E2E)** |
| `e2e-visual-regression.yml` | Visual regression all platforms | push/PR paths | **Merge into e2e-validation** |
| `gpu-tests.yml` | GPU tests (CUDA/MPS) | push/PR/schedule | **Keep** |
| `mesh-sdk.yml` | Rust mesh SDK CI | push/PR paths | **Keep** |
| `metrics-tracking.yml` | Coverage, complexity, deps | push main | **Merge into ci.yml** |
| `nightly-stress.yml` | Adversarial, chaos, soak tests | schedule 2AM | **Keep** |
| `oauth-e2e.yml` | OAuth provider tests | push/PR paths | **Keep** |
| `rust-hub-ci.yml` | Rust hub CI | push/PR paths | **Keep** |
| `safety-verification.yml` | CBF safety verification | push/PR paths | **Keep** |
| `self-healing-ci.yml` | Auto-fix CI failures | workflow_run | **Keep** |
| `smarthome-deploy.yml` | SmartHome Cloud Run deploy | push main paths | **Keep** |
| `unified-screenshots.yml` | Screenshot collection all apps | schedule | **Merge into e2e-validation** |
| `visual-tests.yml` | Prismorphism visual regression | push/PR paths | **Merge into e2e-validation** |

### Target State: 15 Workflows

| Workflow | Consolidates | Platforms |
|----------|--------------|-----------|
| `ci.yml` | + coverage-tracking + metrics-tracking | Python |
| `android-unified.yml` | android-tests + android-xr-tests | Android |
| `apple-unified-builds.yml` | + apple-platform-tests | All Apple |
| `desktop.yml` | (unchanged) | macOS, Linux |
| `rust-hub-ci.yml` | (unchanged) | Rust |
| `mesh-sdk.yml` | (unchanged) | Rust |
| `e2e-unified.yml` | e2e-validation + e2e-visual-regression + unified-screenshots + visual-tests | All platforms |
| `gpu-tests.yml` | (unchanged) | GPU runners |
| `nightly-stress.yml` | (unchanged) | Python |
| `safety-verification.yml` | (unchanged) | Python |
| `oauth-e2e.yml` | (unchanged) | Python |
| `design-tokens.yml` | (unchanged) | All platforms |
| `auto-solver.yml` | (unchanged) | Meta |
| `self-healing-ci.yml` | (unchanged) | Meta |
| `docker-hub-publish.yml` | (unchanged) | Docker |
| `canvas-deploy.yml` | (unchanged) | Deployment |
| `smarthome-deploy.yml` | (unchanged) | Deployment |

## Cascading Triggers

When shared packages change, dependent workflows must run.

### Dependency Graph

```
packages/kagami/ (core)
├── triggers: ci.yml, safety-verification.yml
├── cascades to: android-unified.yml, apple-unified-builds.yml, desktop.yml, e2e-unified.yml
│
packages/kagami-mesh-sdk/ (Rust SDK)
├── triggers: mesh-sdk.yml
├── cascades to: desktop.yml, rust-hub-ci.yml
│
packages/kagami_math/ (math)
├── triggers: ci.yml, gpu-tests.yml
│
packages/kagami_smarthome/ (smart home)
├── triggers: ci.yml, smarthome-deploy.yml
│
config/design-tokens/ (tokens)
├── triggers: design-tokens.yml
├── cascades to: android-unified.yml, apple-unified-builds.yml, desktop.yml
```

### Implementation Pattern

```yaml
# Example: desktop.yml should also trigger on mesh-sdk changes
on:
  push:
    paths:
      - 'apps/desktop/kagami-client/**'
      - 'packages/kagami-mesh-sdk/**'  # Cascade trigger
      - '.github/workflows/desktop.yml'
  workflow_run:
    workflows: ["mesh-sdk"]
    types: [completed]
    branches: [main]
```

## Resilience Features

### 1. Retry Logic for Flaky Tests

```yaml
- name: Run tests with retry
  uses: nick-fields/retry@v3
  with:
    max_attempts: 3
    retry_wait_seconds: 10
    timeout_minutes: 30
    command: pytest tests/integration/ -x
```

### 2. Timeout Protection

All jobs should have explicit timeouts:

| Job Type | Recommended Timeout |
|----------|---------------------|
| Lint | 5-10 minutes |
| Unit tests | 15-20 minutes |
| Integration tests | 20-30 minutes |
| E2E tests | 30-45 minutes |
| Build | 20-30 minutes |
| Deploy | 15-30 minutes |

```yaml
jobs:
  test:
    timeout-minutes: 20
    steps:
      - name: Run tests with step timeout
        timeout-minutes: 15
        run: pytest tests/
```

### 3. Parallel Job Optimization

Use matrix strategies for parallel execution:

```yaml
strategy:
  fail-fast: false  # Don't cancel all jobs on first failure
  matrix:
    os: [ubuntu-latest, macos-latest]
    python-version: ['3.11', '3.12']
    # Max parallel: 4 jobs
```

### 4. Cache Warming

Cache dependencies across workflows:

```yaml
- name: Cache pip
  uses: actions/cache@v4
  with:
    path: ~/.cache/pip
    key: pip-${{ runner.os }}-${{ hashFiles('requirements*.txt') }}
    restore-keys: |
      pip-${{ runner.os }}-

- name: Cache Cargo
  uses: actions/cache@v4
  with:
    path: |
      ~/.cargo/registry
      ~/.cargo/git
      target
    key: cargo-${{ runner.os }}-${{ hashFiles('**/Cargo.lock') }}
```

### 5. Conditional Skipping

Use path filters to skip unchanged components:

```yaml
on:
  pull_request:
    paths:
      - 'apps/ios/**'
      - 'packages/kagami/**'
      - '!**/*.md'  # Ignore documentation changes
```

Use change detection jobs:

```yaml
detect_changes:
  outputs:
    run_ios: ${{ steps.changes.outputs.ios }}
  steps:
    - uses: dorny/paths-filter@v3
      id: changes
      with:
        filters: |
          ios:
            - 'apps/ios/**'

ios_tests:
  needs: detect_changes
  if: needs.detect_changes.outputs.run_ios == 'true'
```

## Workflow Patterns

### Standard Python Workflow

```yaml
name: python-ci

on:
  push:
    branches: [main, develop]
    paths:
      - 'packages/**'
      - 'tests/**'
      - '.github/workflows/python-ci.yml'
  pull_request:
    paths:
      - 'packages/**'
      - 'tests/**'

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

env:
  PYTHON_VERSION: "3.11"

jobs:
  lint:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: pip
      - run: pip install ruff mypy
      - run: ruff check packages/ tests/
      - run: mypy packages/ --ignore-missing-imports

  test:
    needs: lint
    runs-on: ${{ matrix.os }}
    timeout-minutes: 20
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest]
        python-version: ['3.11', '3.12']
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: pip
      - run: pip install -r requirements.txt -r requirements-dev.txt
      - run: pip install -e .
      - run: pytest tests/ -n auto --cov

  security:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      - run: pip install bandit safety pip-audit
      - run: bandit -r packages/ -ll
      - run: safety check
```

### Standard Rust Workflow

```yaml
name: rust-ci

on:
  push:
    paths:
      - 'apps/hub/**'
      - 'Cargo.lock'
  pull_request:
    paths:
      - 'apps/hub/**'

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

env:
  CARGO_TERM_COLOR: always
  RUST_BACKTRACE: 1

jobs:
  lint:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - uses: dtolnay/rust-toolchain@stable
        with:
          components: rustfmt, clippy
      - uses: actions/cache@v4
        with:
          path: |
            ~/.cargo/registry
            ~/.cargo/git
            target
          key: cargo-lint-${{ hashFiles('**/Cargo.lock') }}
      - run: cargo fmt --all -- --check
      - run: cargo clippy --all-targets -- -D warnings

  test:
    needs: lint
    runs-on: ${{ matrix.os }}
    timeout-minutes: 30
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest]
    steps:
      - uses: actions/checkout@v4
      - uses: dtolnay/rust-toolchain@stable
      - uses: actions/cache@v4
        with:
          path: |
            ~/.cargo/registry
            ~/.cargo/git
            target
          key: cargo-test-${{ matrix.os }}-${{ hashFiles('**/Cargo.lock') }}
      - run: cargo test --all

  security:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - uses: dtolnay/rust-toolchain@stable
      - run: cargo install cargo-audit
      - run: cargo audit
```

### Standard Apple Workflow

```yaml
name: apple-ci

on:
  push:
    paths:
      - 'apps/ios/**'
      - 'apps/watch/**'
      - 'apps/vision/**'
  pull_request:
    paths:
      - 'apps/ios/**'
      - 'apps/watch/**'
      - 'apps/vision/**'

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

env:
  XCODE_VERSION: "15.4"

jobs:
  build:
    runs-on: macos-14
    timeout-minutes: 30
    strategy:
      fail-fast: false
      matrix:
        platform: [iOS, watchOS, visionOS]
    steps:
      - uses: actions/checkout@v4
      - run: sudo xcode-select -s /Applications/Xcode_${{ env.XCODE_VERSION }}.app
      - uses: actions/cache@v4
        with:
          path: |
            .build
            ~/Library/Caches/org.swift.swiftpm
          key: spm-${{ matrix.platform }}-${{ hashFiles('**/Package.swift') }}
      - run: swift package resolve
      - run: xcodebuild build -scheme Kagami${{ matrix.platform }} -destination "platform=${{ matrix.platform }} Simulator" CODE_SIGNING_ALLOWED=NO
```

## Job Dependencies

```
ci.yml
├── detect_changes
├── ruff (parallel)
├── mypy (parallel)
├── test_unit (needs: ruff, mypy, detect_changes)
├── test_systems (needs: ruff, mypy)
├── test_integration (needs: ruff, mypy, detect_changes)
├── test_e2e (needs: ruff, mypy, detect_changes)
├── security (needs: ruff, mypy)
├── coverage (needs: ruff, mypy)
├── quality (needs: ruff, mypy)
├── docs (needs: ruff, mypy)
├── performance_regression (needs: ruff, mypy)
└── deploy (needs: test_unit, test_systems, test_integration, test_e2e, security)
    ├── rollback (if: deploy fails)
    └── notify_rollback (if: rollback succeeds)
```

## Monitoring and Alerts

### Auto-Solver Integration

When CI fails, `auto-solver.yml` automatically:
1. Creates a Linear issue with failure details
2. Sends Slack notification
3. Logs to Notion database

### Self-Healing CI

When CI fails, `self-healing-ci.yml` automatically:
1. Analyzes failure logs with Claude API
2. Generates fix suggestions
3. Creates draft PR with fixes
4. Records learning for continuous improvement

## Scheduled Workflows

| Workflow | Schedule | Purpose |
|----------|----------|---------|
| `coverage-tracking.yml` | Monday 00:00 UTC | Weekly coverage trends |
| `gpu-tests.yml` | Daily 02:00 UTC | Nightly GPU tests |
| `nightly-stress.yml` | Daily 02:00 UTC | Adversarial/chaos tests |
| `unified-screenshots.yml` | Daily 04:00 UTC | Screenshot collection |

## Cost Optimization

1. **Use path filters** - Only run on relevant changes
2. **Cancel in-progress** - Cancel duplicate runs
3. **Fail fast** - Lint before expensive tests
4. **Cache aggressively** - Pip, cargo, SPM, npm
5. **Self-hosted runners** - For GPU tests and frequent runs
6. **Conditional jobs** - Skip unchanged platforms

## Migration Plan

### Phase 1: Merge Redundant Workflows (Week 1)
1. ~~Merge `android-xr-tests.yml` into `android-tests.yml`~~ DONE: Consolidated into `android-unified.yml`
2. Merge `apple-platform-tests.yml` into `apple-unified-builds.yml`
3. Merge `coverage-tracking.yml` and `metrics-tracking.yml` into `ci.yml`

### Phase 2: Consolidate E2E Workflows (Week 2)
1. Merge `e2e-visual-regression.yml` into `e2e-validation.yml`
2. Merge `unified-screenshots.yml` into `e2e-validation.yml`
3. Merge `visual-tests.yml` into `e2e-validation.yml`

### Phase 3: Add Resilience Features (Week 3)
1. Add retry logic to flaky tests
2. Add explicit timeouts to all jobs
3. Optimize parallel execution
4. Improve caching

### Phase 4: Implement Cascading Triggers (Week 4)
1. Add workflow_run triggers for dependencies
2. Update path filters for shared packages
3. Test cascading behavior

---

*Generated by Kagami CI Architecture Analysis*
*h(x) >= 0. Always.*
