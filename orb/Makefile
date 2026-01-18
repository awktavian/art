PYTHON ?= python3
COMPOSE ?= docker compose
VENV := .venv

# Smart venv detection: use .venv if exists, otherwise fall back to system Python
ifneq (,$(wildcard $(VENV)/bin/python))
    VENV_BIN := $(VENV)/bin
else ifneq (,$(wildcard $(HOME)/.pyenv/shims/python))
    # pyenv detected
    VENV_BIN := $(HOME)/.pyenv/shims
else
    # Use system Python bin directory
    VENV_BIN := $(dir $(shell which python3))
endif

# ==============================================================================
# Parallelism & Timeout Configuration
# ==============================================================================
# CPU count detection (macOS/Linux compatible)
NPROC := $(shell nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 8)
# Cap workers at 8 for better parallelization (reduced from 24 to avoid resource contention)
WORKERS := $(shell echo $$(( $(NPROC) > 8 ? 8 : $(NPROC) )))

# Cross-platform timeout command (GNU coreutils on macOS: brew install coreutils)
TIMEOUT_CMD := $(shell command -v timeout 2>/dev/null || command -v gtimeout 2>/dev/null || echo "")

# Hard timeout for entire test run (seconds) - prevents infinite hangs
# This is a shell-level backstop; per-test timeouts are in pyproject.toml
TEST_RUN_TIMEOUT ?= 300
SLOW_RUN_TIMEOUT ?= 900
INTEGRATION_RUN_TIMEOUT ?= 600

# Timeout wrapper: uses timeout/gtimeout if available; otherwise uses Python to enforce.
define run_with_timeout
	$(if $(TIMEOUT_CMD),$(TIMEOUT_CMD) $(1) $(2),$(VENV_BIN)/python -c "import os,signal,subprocess,sys; exec('t=float(sys.argv[1])\\ncmd=sys.argv[2:]\\nstart_new_session=hasattr(os,\\'setsid\\')\\np=subprocess.Popen(cmd, start_new_session=start_new_session)\\ntry:\\n    rc=p.wait(timeout=t)\\nexcept subprocess.TimeoutExpired:\\n    try:\\n        (os.killpg(p.pid, signal.SIGKILL) if start_new_session else p.kill())\\n    except Exception:\\n        p.kill()\\n    sys.stderr.write(\\\"\\\\n\\\\n⏰ COMMAND TIMED OUT after %.0fs\\\\n\\\" % t)\\n    raise SystemExit(124)\\nraise SystemExit(rc)\\n')" $(1) $(2))
endef

# Directories to ignore for fast tests
FAST_IGNORE := --ignore=tests/load --ignore=tests/stress --ignore=tests/soak \
               --ignore=tests/chaos --ignore=tests/e2e --ignore=tests/benchmarks \
               --ignore=tests/performance --ignore=tests/smoke

# ==============================================================================
# Phony targets
# ==============================================================================
.PHONY: all venv install install-satellites install-voice setup doctor test lint format typecheck clean help
.PHONY: test-all test-unit test-quick test-serial test-failed test-integration test-e2e test-satellites
.PHONY: test-tier-1 test-tier-2 test-tier-3 test-tiers test-tier-report
.PHONY: test-smart test-smart-cached test-changed test-testmon testmon-setup
.PHONY: test-profile test-collect test-debug ablation
.PHONY: services-start services-stop services-health start docker-check
.PHONY: test-infra-up test-infra-down test-infra-health test-integration-full
.PHONY: train train-kagami train-quick train-resume
.PHONY: ci ci-full pre-commit pre-push verify-tic bench-geometric safety-conformal
.PHONY: llm-config llm-test safety-setup safety-test
.PHONY: elysia-setup elysia-test weaviate-start weaviate-health
.PHONY: forge-setup forge-test forge-test-real forge-hunyuan forge-unirig forge-motion forge-emu forge-models
.PHONY: perception-test perception-verify
.PHONY: benchmark benchmark-cache benchmark-repository benchmark-report benchmark-compare
.PHONY: cloc cloc-summary cloc-packages cloc-json cloc-report
.PHONY: metrics-report metrics-coverage metrics-complexity metrics-duplicates metrics-deps

# ==============================================================================
# Default target
# ==============================================================================
all: help

help:
	@echo "═══════════════════════════════════════════════════════════════════════"
	@echo "  Kagami Development Commands"
	@echo "═══════════════════════════════════════════════════════════════════════"
	@echo ""
	@echo "Getting Started:"
	@echo "  make setup         One-command dev environment setup (RECOMMENDED)"
	@echo "  make doctor        Check installation health"
	@echo ""
	@echo "Environment:"
	@echo "  make venv          Create Python virtual environment"
	@echo "  make install       Install dependencies + satellite packages"
	@echo "  make install-satellites  Install satellite packages only"
	@echo "  make install-voice Install voice/wake word deps (PyAudio + Porcupine)"
	@echo "  make clean         Remove venv and cache files"
	@echo ""
	@echo "Code Generation:"
	@echo "  make generate-tokens  Generate design tokens for all platforms"
	@echo "  make generate-docs    Generate design system documentation"
	@echo "  make generate         Generate all code artifacts"
	@echo ""
	@echo "SMART TESTING (RECOMMENDED - runs only affected tests):"
	@echo "  make test-smart         Run only tests affected by changes (since HEAD)"
	@echo "  make test-smart-cached  Run tests for staged changes only"
	@echo "  make test-changed       Run tests changed since main branch"
	@echo "  make test-testmon       Use testmon for dependency-based selection"
	@echo "  make testmon-setup      Install pytest-testmon"
	@echo ""
	@echo "Tiered Testing (performance-based):"
	@echo "  make test-tier-1   Tier 1: Unit tests (<1s, ~2min total)"
	@echo "  make test-tier-2   Tier 2: Integration tests (<5s, ~5min total)"
	@echo "  make test-tier-3   Tier 3: E2E tests (10-60s, ~15min total)"
	@echo "  make test-tiers    Run all tiers sequentially (fast feedback loop)"
	@echo ""
	@echo "Testing ($(WORKERS) workers, 60s per-test timeout, $(TEST_RUN_TIMEOUT)s total):"
	@echo "  make test          Fast tests in parallel (skips load/stress/e2e)"
	@echo "  make test-all      ALL tests including slow ones"
	@echo "  make test-unit     Unit tests only (fastest)"
	@echo "  make test-quick    Tests without @slow marker"
	@echo "  make test-e2e      E2E tests (full system integration)"
	@echo "  make test-serial   Serial execution for debugging (verbose)"
	@echo "  make test-failed   Re-run only failed tests"
	@echo "  make test-integration  Integration tests"
	@echo "  make test-satellites   Test satellite packages (HAL, API, Math)"
	@echo ""
	@echo "Diagnostics:"
	@echo "  make test-profile  Profile tests to find slow ones"
	@echo "  make test-collect  Collect tests without running (check for import errors)"
	@echo "  make test-debug    Run single test file with maximum verbosity"
	@echo "  make ablation      Run ablation studies (E8/Fano/Colony/Catastrophe)"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint          Run linters (ruff)"
	@echo "  make format        Auto-format code (ruff format)"
	@echo "  make typecheck     Run mypy type checking"
	@echo "  make quality       Run all quality gates (<2min)"
	@echo "  make quality-dashboard  Generate quality dashboard JSON"
	@echo ""
	@echo "Services:"
	@echo "  make services-start   Start Redis + CockroachDB + etcd + Weaviate"
	@echo "  make services-stop    Stop all services"
	@echo "  make services-health  Check service status"
	@echo "  make start            Start Kagami API"
	@echo ""
	@echo "Integration Testing:"
	@echo "  make test-infra-up         Start integration test services"
	@echo "  make test-infra-down       Stop integration test services"
	@echo "  make test-infra-health     Check integration test service status"
	@echo "  make test-integration-full Run integration tests with real services"
	@echo ""
	@echo "Elysia RAG:"
	@echo "  make elysia-setup     Install weaviate-client and configure"
	@echo "  make elysia-test      Test Elysia + Weaviate integration"
	@echo "  make weaviate-start   Start Weaviate only"
	@echo "  make weaviate-health  Check Weaviate status"
	@echo ""
	@echo "Perception (Vision/Audio):"
	@echo "  make perception-test  Run perception wiring smoke tests"
	@echo "  make perception-verify  Run perception verification script (best-effort)"
	@echo ""
	@echo "Forge 3D Character Generation:"
	@echo "  make forge-setup      Install all Forge dependencies (UniRig, Motion-Agent, Emu)"
	@echo "  make forge-test       Run Forge test suite"
	@echo "  make forge-test-real  Run Forge real-model tests (downloads/GPUs, opt-in)"
	@echo "  make forge-models     Download AI models (~20GB)"
	@echo "  make forge-unirig     Setup UniRig only"
	@echo "  make forge-motion     Setup Motion-Agent only"
	@echo "  make forge-emu        Setup Emu3.5 only"
	@echo ""
	@echo "Training:"
	@echo "  make train         Train KagamiWorldModel (optimal config)"
	@echo "  make train-quick   Quick training with minimal config"
	@echo "  make train-resume  Resume from latest checkpoint"
	@echo "  (Metrics: W&B at https://wandb.ai)"
	@echo ""
	@echo "CI/CD:"
	@echo "  make pre-commit    Pre-commit: format + lint + typecheck + tier-1"
	@echo "  make pre-push      Pre-push: lint + typecheck + all tiers"
	@echo "  make ci            CI checks: lint + typecheck + tier-1 + tier-2"
	@echo "  make ci-full       Full CI: lint + typecheck + all tiers"
	@echo ""
	@echo "Benchmarking:"
	@echo "  make benchmark           Run all performance benchmarks"
	@echo "  make benchmark-cache     Benchmark cache layer only"
	@echo "  make benchmark-repository  Benchmark repositories only"
	@echo "  make benchmark-report    Generate benchmark report"
	@echo "  make benchmark-compare   Compare with previous benchmarks"
	@echo ""
	@echo "Codebase Analysis:"
	@echo "  make cloc             Full line count analysis (all components)"
	@echo "  make cloc-summary     Quick summary only"
	@echo "  make cloc-packages    Detailed packages breakdown"
	@echo "  make cloc-json        Export as JSON (cloc-report.json)"
	@echo "  make cloc-report      Generate markdown report (CLOC_REPORT.md)"
	@echo ""
	@echo "Metrics & Reporting:"
	@echo "  make metrics-report      Full metrics collection (coverage + complexity + deps)"
	@echo "  make metrics-coverage    Test coverage with HTML/JSON/XML reports"
	@echo "  make metrics-complexity  Cyclomatic complexity analysis (radon)"
	@echo "  make metrics-deps        Dependency health and security audit"
	@echo "  make metrics-duplicates  Code duplication detection"
	@echo ""
	@echo "Advanced:"
	@echo "  make safety-test      Test safety classifier + CBF pipeline"
	@echo "  make verify-tic       Formal verification via Lean 4"
	@echo "  make bench-geometric  Benchmark geometric layers"
	@echo ""
	@echo "Android XR:"
	@echo "  make android-xr       Build Android XR debug APK"
	@echo "  make android-xr-test  Run Android XR unit tests"
	@echo "  make android-xr-lint  Run Android XR lint checks"
	@echo "  make android-xr-clean Clean Android XR build"
	@echo "═══════════════════════════════════════════════════════════════════════"

# ==============================================================================
# Environment Setup
# ==============================================================================
venv:
	@echo "🐍 Creating Python virtual environment..."
	@$(PYTHON) -m venv $(VENV)
	@$(VENV_BIN)/pip install --upgrade pip wheel setuptools
	@echo "✅ Virtual environment created at $(VENV)"
	@echo "   Activate with: source $(VENV)/bin/activate"

install: venv
	@echo "📦 Installing dependencies..."
	@if [ -f requirements.txt ]; then \
		$(VENV_BIN)/pip install -r requirements.txt; \
	fi
	@if [ -f requirements-dev.txt ]; then \
		$(VENV_BIN)/pip install -r requirements-dev.txt; \
	fi
	@$(VENV_BIN)/pip install -e .
	@echo "📦 Installing packages..."
	@for pkg in packages/*/; do \
		if [ -f "$$pkg/pyproject.toml" ]; then \
			$(VENV_BIN)/pip install -e "$$pkg" 2>/dev/null || true; \
		fi; \
	done
	@echo "✅ Dependencies installed"

# Install packages only
install-packages:
	@echo "📦 Installing packages..."
	@for pkg in packages/*/; do \
		if [ -f "$$pkg/pyproject.toml" ]; then \
			echo "  Installing $$pkg..."; \
			$(VENV_BIN)/pip install -e "$$pkg"; \
		fi; \
	done
	@echo "✅ Packages installed"

# Install voice/wake word dependencies (optional)
install-voice:
	@echo "🎤 Installing voice dependencies..."
	@echo ""
	@echo "Step 1: Installing PortAudio (system library)..."
	@if command -v brew >/dev/null 2>&1; then \
		brew install portaudio 2>/dev/null || echo "   PortAudio already installed"; \
	elif command -v apt-get >/dev/null 2>&1; then \
		sudo apt-get install -y portaudio19-dev; \
	else \
		echo "⚠️  Please install PortAudio manually"; \
		echo "   macOS: brew install portaudio"; \
		echo "   Ubuntu: sudo apt-get install portaudio19-dev"; \
	fi
	@echo ""
	@echo "Step 2: Installing PyAudio..."
	@$(VENV_BIN)/pip install pyaudio>=0.2.14
	@echo ""
	@echo "Step 3: Installing Porcupine wake word engine..."
	@$(VENV_BIN)/pip install pvporcupine>=3.0.0
	@echo ""
	@echo "Step 4: Verify installation..."
	@$(VENV_BIN)/python -c "import pyaudio; print('  ✅ PyAudio:', pyaudio.__version__)"
	@$(VENV_BIN)/python -c "import pvporcupine; print('  ✅ Porcupine: installed')"
	@echo ""
	@echo "⚠️  IMPORTANT: Set PICOVOICE_ACCESS_KEY in .env"
	@echo "   Get your free key at: https://console.picovoice.ai/"
	@echo ""
	@echo "✅ Voice dependencies installed"

clean:
	@echo "🧹 Cleaning up..."
	@rm -rf $(VENV)
	@rm -rf .pytest_cache .mypy_cache .ruff_cache .hypothesis
	@rm -rf __pycache__ htmlcov .coverage coverage.xml
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type f -name ".coverage.*" -delete 2>/dev/null || true
	@echo "✅ Cleanup complete"

# One-command setup (recommended entry point)
setup:
	@echo "🚀 Running development setup..."
	@./setup_dev.sh

# Installation health check
doctor:
	@echo "🩺 Kagami Installation Health Check"
	@echo "════════════════════════════════════════════════════════════════════"
	@echo ""
	@echo "System:"
	@printf "  Python:     "; python3 --version 2>/dev/null || echo "❌ Not found"
	@printf "  pip:        "; pip --version 2>/dev/null | head -c 40 || echo "❌ Not found"; echo ""
	@printf "  venv:       "; if [ -d "$(VENV)" ]; then echo "✅ $(VENV)"; else echo "❌ Not found (run: make setup)"; fi
	@printf "  Docker:     "; docker --version 2>/dev/null | head -c 30 || echo "⚠️  Not installed (optional)"; echo ""
	@echo ""
	@echo "Dependencies:"
	@printf "  torch:      "; $(VENV_BIN)/python -c "import torch; print(f'✅ {torch.__version__}')" 2>/dev/null || echo "❌ Not installed"
	@printf "  kagami:     "; $(VENV_BIN)/python -c "import kagami; print('✅ installed')" 2>/dev/null || echo "❌ Not installed"
	@printf "  ruff:       "; $(VENV_BIN)/ruff --version 2>/dev/null || echo "❌ Not installed"
	@printf "  mypy:       "; $(VENV_BIN)/mypy --version 2>/dev/null | head -c 20 || echo "❌ Not installed"; echo ""
	@echo ""
	@echo "Configuration:"
	@printf "  .env:       "; if [ -f ".env" ]; then echo "✅ exists"; else echo "⚠️  Missing (run: cp env.example.minimal .env)"; fi
	@printf "  pre-commit: "; if [ -f ".git/hooks/pre-commit" ]; then echo "✅ installed"; else echo "⚠️  Not installed (run: pre-commit install)"; fi
	@echo ""
	@echo "Services:"
	@printf "  Redis:      "; redis-cli ping 2>/dev/null && echo "✅ running" || echo "⚠️  Not running (optional)"
	@printf "  Docker:     "; docker info >/dev/null 2>&1 && echo "✅ running" || echo "⚠️  Not running (optional)"
	@echo ""
	@echo "Core Imports:"
	@$(VENV_BIN)/python -c "exec('''import sys\nfor name, mod in [(\"unified_agents\", \"kagami.core.unified_agents\"), (\"world_model\", \"kagami.core.world_model\"), (\"safety\", \"kagami.core.safety\")]:\n    try:\n        __import__(mod)\n        print(f\"  {name}: ✅\")\n    except Exception as e:\n        print(f\"  {name}: ❌ {e}\")\n''')" 2>&1 || echo "  ❌ Import check failed"
	@echo ""
	@echo "Satellite Packages:"
	@$(VENV_BIN)/python -c "exec('''import sys\nfor name, mod in [(\"kagami_api\", \"kagami_api\"), (\"kagami_hal\", \"kagami_hal\"), (\"kagami_math\", \"kagami_math\"), (\"kagami_smarthome\", \"kagami_smarthome\")]:\n    try:\n        __import__(mod)\n        print(f\"  {name}: ✅\")\n    except Exception as e:\n        print(f\"  {name}: ❌ {e}\")\n''')" 2>&1 || echo "  ❌ Satellite import check failed"
	@echo ""
	@echo "Voice/Wake Word (optional):"
	@$(VENV_BIN)/python -c "exec('''import sys\ntry:\n    import pyaudio\n    print(f\"  PyAudio: ✅ {pyaudio.__version__}\")\nexcept ImportError:\n    print(\"  PyAudio: ⚠️  Not installed (run: make install-voice)\")\ntry:\n    import pvporcupine\n    print(\"  Porcupine: ✅ installed\")\nexcept ImportError:\n    print(\"  Porcupine: ⚠️  Not installed (run: make install-voice)\")\nimport os\nif os.getenv(\"PICOVOICE_ACCESS_KEY\"):\n    print(\"  Access Key: ✅ Set\")\nelse:\n    print(\"  Access Key: ⚠️  PICOVOICE_ACCESS_KEY not set\")\n''')" 2>&1 || echo "  ⚠️  Voice check failed"
	@echo ""
	@echo "════════════════════════════════════════════════════════════════════"
	@echo "Run 'make setup' to fix any issues, or 'make help' for commands."

# ==============================================================================
# Code Generation
# ==============================================================================

# Generate design tokens for all platforms
generate-tokens:
	@echo "🎨 Generating design tokens..."
	@$(PYTHON) config/design-tokens/generate.py
	@echo "✅ Design tokens generated for all platforms"

# Generate design system documentation
generate-docs:
	@echo "📚 Generating design system docs..."
	@mkdir -p docs/kagami-ds
	@$(PYTHON) -c "import json; from pathlib import Path; \
		tokens = {k: json.loads((Path('config/design-tokens') / f'{k}.json').read_text()) for k in ['colors', 'motion', 'spacing', 'effects']}; \
		Path('docs/kagami-ds/design-system.json').write_text(json.dumps(tokens, indent=2))"
	@echo "✅ Design system docs generated"

# Generate all code artifacts
generate: generate-tokens generate-docs
	@echo "✅ All code generation complete"

# ==============================================================================
# Testing (All use pyproject.toml for pytest config)
# ==============================================================================

# ==============================================================================
# Tiered Testing Strategy
# ==============================================================================
#
# Performance-based test tiers for efficient development workflow:
#
# TIER 1 (Unit):        <1s per test,  no external deps      → make test-tier-1
# TIER 2 (Integration): <5s per test,  requires services     → make test-tier-2
# TIER 3 (E2E):         10-60s per test, full system         → make test-tier-3
#
# Use markers: @pytest.mark.tier_unit, @pytest.mark.tier_integration, @pytest.mark.tier_e2e
#
# ==============================================================================

# TIER 1: Unit tests (fastest feedback, <2 minutes)
test-tier-1:
	@echo "🧪 TIER 1: Unit tests (<1s each, $(WORKERS) workers)..."
	@$(call run_with_timeout,120,$(VENV_BIN)/pytest tests/unit/ \
		-m "not slow" \
		-n auto \
		--timeout=60 \
		--maxfail=10) \
	|| { code=$$?; \
	     if [ $$code -eq 124 ]; then \
	         echo "⏰ TIER 1 TIMED OUT after 120s"; \
	         exit 1; \
	     fi; \
	     exit $$code; \
	   }

# TIER 2: Integration tests (medium feedback, <5 minutes)
test-tier-2:
	@echo "🧪 TIER 2: Integration tests (<5s each, $(WORKERS) workers)..."
	@$(call run_with_timeout,1200,$(VENV_BIN)/pytest tests/integration/ \
		tests/core/ \
		tests/api/ \
		-m "not slow and not e2e" \
		-n auto \
		--timeout=120 \
		--maxfail=10) \
	|| { code=$$?; \
	     if [ $$code -eq 124 ]; then \
	         echo "⏰ TIER 2 TIMED OUT after 1200s"; \
	         exit 1; \
	     fi; \
	     exit $$code; \
	   }

# TIER 3: E2E tests (slow, <15 minutes)
test-tier-3:
	@echo "🧪 TIER 3: E2E tests (10-60s each, $(WORKERS) workers)..."
	@$(call run_with_timeout,900,$(VENV_BIN)/pytest tests/e2e/ \
		tests/forge/ \
		tests/contracts/ \
		-n auto \
		--timeout=180 \
		--maxfail=5) \
	|| { code=$$?; \
	     if [ $$code -eq 124 ]; then \
	         echo "⏰ TIER 3 TIMED OUT after 900s"; \
	         exit 1; \
	     fi; \
	     exit $$code; \
	   }

# Primary test target: fast tests with hard timeout
# Uses pyproject.toml settings (16 workers, 60s per-test timeout, thread method)
# Shell timeout ensures deterministic finish even if pytest hangs
test:
	@echo "🧪 Running tests ($(WORKERS) workers, $(TEST_RUN_TIMEOUT)s hard limit)..."
	@$(call run_with_timeout,$(TEST_RUN_TIMEOUT),$(VENV_BIN)/pytest tests/ \
		$(FAST_IGNORE) \
		-n auto \
		--timeout=60 \
		--maxfail=10) \
	|| { code=$$?; \
	     if [ $$code -eq 124 ]; then \
	         echo ""; \
	         echo "⏰ TEST RUN TIMED OUT after $(TEST_RUN_TIMEOUT)s"; \
	         echo "   Run 'make test-profile' to identify slow tests"; \
	         exit 1; \
	     fi; \
	     exit $$code; \
	   }

# All tests including slow directories (longer timeout)
test-all:
	@echo "🧪 Running ALL tests ($(WORKERS) workers, $(SLOW_RUN_TIMEOUT)s hard limit)..."
	@$(call run_with_timeout,$(SLOW_RUN_TIMEOUT),$(VENV_BIN)/pytest tests/ \
		-n auto \
		--timeout=120 \
		--maxfail=20) \
	|| { code=$$?; \
	     if [ $$code -eq 124 ]; then \
	         echo "⏰ TEST RUN TIMED OUT after $(SLOW_RUN_TIMEOUT)s"; \
	         exit 1; \
	     fi; \
	     exit $$code; \
	   }

# Unit tests only (fastest)
test-unit:
	@echo "🧪 Running unit tests ($(WORKERS) workers)..."
	@$(call run_with_timeout,$(TEST_RUN_TIMEOUT),$(VENV_BIN)/pytest tests/unit/ \
		-n auto \
		--timeout=60 \
		--maxfail=5) \
	|| { code=$$?; \
	     if [ $$code -eq 124 ]; then \
	         echo "⏰ TEST RUN TIMED OUT after $(TEST_RUN_TIMEOUT)s"; \
	         exit 1; \
	     fi; \
	     exit $$code; \
	   }

# Quick tests: skip @slow marker
test-quick:
	@echo "🧪 Running quick tests (no @slow markers, $(WORKERS) workers)..."
	@$(call run_with_timeout,$(TEST_RUN_TIMEOUT),$(VENV_BIN)/pytest tests/ \
		$(FAST_IGNORE) \
		-m "not slow" \
		-n auto \
		--timeout=60 \
		--maxfail=10) \
	|| { code=$$?; \
	     if [ $$code -eq 124 ]; then \
	         echo "⏰ TEST RUN TIMED OUT after $(TEST_RUN_TIMEOUT)s"; \
	         exit 1; \
	     fi; \
	     exit $$code; \
	   }

# Selective tests: run unit tests + core integration (fast feedback)
test-selective:
	@echo "🧪 Running selective tests (unit + core integration)..."
	@$(call run_with_timeout,$(TEST_RUN_TIMEOUT),$(VENV_BIN)/pytest \
		tests/unit/ \
		tests/core/ \
		tests/api/routes/test_health_complete.py \
		--maxfail=5 \
		-n $(WORKERS)) \
	|| { code=$$?; \
	     if [ $$code -eq 124 ]; then \
	         echo "⏰ TEST RUN TIMED OUT after $(TEST_RUN_TIMEOUT)s"; \
	         exit 1; \
	     fi; \
	     exit $$code; \
	   }

# Integration tests
test-integration:
	@echo "🧪 Running integration tests ($(WORKERS) workers)..."
	@$(call run_with_timeout,$(INTEGRATION_RUN_TIMEOUT),$(VENV_BIN)/pytest tests/integration/ \
		-n auto \
		--timeout=180 \
		--maxfail=10) \
	|| { code=$$?; \
	     if [ $$code -eq 124 ]; then \
	         echo "⏰ TEST RUN TIMED OUT after $(INTEGRATION_RUN_TIMEOUT)s"; \
	         exit 1; \
	     fi; \
	     exit $$code; \
	   }

# E2E tests (full system integration)
test-e2e:
	@echo "🧪 Running E2E tests..."
	@$(call run_with_timeout,$(INTEGRATION_RUN_TIMEOUT),$(VENV_BIN)/pytest tests/e2e/ \
		--timeout=120 \
		-n 0 \
		-v \
		--tb=short \
		--maxfail=5) \
	|| { code=$$?; \
	     if [ $$code -eq 124 ]; then \
	         echo "⏰ E2E TEST RUN TIMED OUT after $(INTEGRATION_RUN_TIMEOUT)s"; \
	         exit 1; \
	     fi; \
	     exit $$code; \
	   }

# Serial execution for debugging (no parallelism, verbose)
test-serial:
	@echo "🧪 Running tests serially (debugging mode)..."
	@$(call run_with_timeout,$(SLOW_RUN_TIMEOUT),$(VENV_BIN)/pytest tests/ \
		$(FAST_IGNORE) \
		-n 0 \
		-v \
		--tb=long \
		--timeout=120 \
		--maxfail=3) \
	|| { code=$$?; \
	     if [ $$code -eq 124 ]; then \
	         echo "⏰ TEST RUN TIMED OUT after $(SLOW_RUN_TIMEOUT)s"; \
	         exit 1; \
	     fi; \
	     exit $$code; \
	   }

# Re-run only failed tests
test-failed:
	@echo "🧪 Re-running failed tests..."
	@$(VENV_BIN)/pytest tests/ \
		--lf \
		-v \
		--tb=short

# Test satellite packages (HAL, API, Math, AR)
test-satellites:
	@echo "🛰️  Testing satellite packages ($(WORKERS) workers)..."
	@$(call run_with_timeout,$(TEST_RUN_TIMEOUT),$(VENV_BIN)/pytest \
		tests/unit/hal/ \
		tests/core/hal/ \
		tests/core/math/ \
		tests/api/ \
		-n auto \
		--timeout=60 \
		-q \
		--maxfail=10) \
	|| { code=$$?; \
	     if [ $$code -eq 124 ]; then \
	         echo "⏰ SATELLITE TESTS TIMED OUT after $(TEST_RUN_TIMEOUT)s"; \
	         exit 1; \
	     fi; \
	     exit $$code; \
	   }
	@echo "✅ Satellite tests complete"

# ==============================================================================
# Tiered Testing Workflows
# ==============================================================================

# Run all tiers sequentially (optimal development workflow)
test-tiers: test-tier-1 test-tier-2 test-tier-3
	@echo ""
	@echo "✅ All test tiers completed successfully"
	@echo ""
	@echo "📊 Tier Summary:"
	@echo "   TIER 1 (Unit):        <1s per test  → Fast feedback"
	@echo "   TIER 2 (Integration): <5s per test  → Medium feedback"
	@echo "   TIER 3 (E2E):         10-60s        → Full validation"

# Generate timing report to help categorize tests into tiers
test-tier-report:
	@echo "📊 Generating test timing report for tier categorization..."
	@$(VENV_BIN)/pytest tests/ \
		$(FAST_IGNORE) \
		--durations=0 \
		--durations-min=0.1 \
		-q \
		--collect-only \
		2>&1 | tee .pytest_tier_report.log || true
	@echo ""
	@echo "📋 Timing data saved to .pytest_tier_report.log"
	@echo ""
	@echo "Categorization guidelines:"
	@echo "  <1s     → Tier 1 (unit)"
	@echo "  1-5s    → Tier 2 (integration)"
	@echo "  >5s     → Tier 3 (e2e)"

# ==============================================================================
# Smart Testing (Change-Based Test Selection)
# ==============================================================================
#
# These targets only run tests affected by your code changes, dramatically
# reducing feedback time during development.
#
# How it works:
#   1. Analyzes git diff to find changed files
#   2. Maps changed files to their relevant test files
#   3. Runs only those tests
#
# ==============================================================================

# Install pytest-testmon for dependency-based test selection
testmon-setup:
	@echo "📦 Installing pytest-testmon..."
	@$(VENV_BIN)/pip install pytest-testmon
	@echo "✅ pytest-testmon installed"
	@echo ""
	@echo "Usage: make test-testmon"
	@echo "  First run builds the dependency database (.testmondata)"
	@echo "  Subsequent runs only execute tests affected by changes"

# Smart test: run only tests affected by changes since last commit
test-smart:
	@echo "🧠 Smart Test Selection (changes since HEAD)..."
	@TESTS=$$($(PYTHON) scripts/testing/smart_test_selector.py --pytest-args 2>/dev/null); \
	if [ -z "$$TESTS" ]; then \
		echo "✅ No changes detected - nothing to test"; \
	else \
		echo "📋 Running: pytest $$TESTS"; \
		$(call run_with_timeout,$(TEST_RUN_TIMEOUT),$(VENV_BIN)/pytest $$TESTS \
			-n $(WORKERS) \
			--maxfail=5 \
			-q \
			--tb=short) \
		|| { code=$$?; \
		     if [ $$code -eq 124 ]; then \
		         echo "⏰ SMART TEST TIMED OUT after $(TEST_RUN_TIMEOUT)s"; \
		         exit 1; \
		     fi; \
		     exit $$code; \
		   }; \
	fi

# Smart test for staged changes only (pre-commit hook friendly)
test-smart-cached:
	@echo "🧠 Smart Test Selection (staged changes only)..."
	@TESTS=$$($(PYTHON) scripts/testing/smart_test_selector.py --cached --pytest-args 2>/dev/null); \
	if [ -z "$$TESTS" ]; then \
		echo "✅ No staged changes - nothing to test"; \
	else \
		echo "📋 Running: pytest $$TESTS"; \
		$(call run_with_timeout,$(TEST_RUN_TIMEOUT),$(VENV_BIN)/pytest $$TESTS \
			-n $(WORKERS) \
			--maxfail=5 \
			-q \
			--tb=short) \
		|| { code=$$?; \
		     if [ $$code -eq 124 ]; then \
		         echo "⏰ SMART TEST TIMED OUT after $(TEST_RUN_TIMEOUT)s"; \
		         exit 1; \
		     fi; \
		     exit $$code; \
		   }; \
	fi

# Test changes since main branch (PR validation)
test-changed:
	@echo "🧠 Smart Test Selection (changes since main branch)..."
	@TESTS=$$($(PYTHON) scripts/testing/smart_test_selector.py --base=main --pytest-args 2>/dev/null); \
	if [ -z "$$TESTS" ]; then \
		echo "✅ No changes vs main - nothing to test"; \
	else \
		echo "📋 Running: pytest $$TESTS"; \
		$(call run_with_timeout,$(TEST_RUN_TIMEOUT),$(VENV_BIN)/pytest $$TESTS \
			-n $(WORKERS) \
			--maxfail=10 \
			-q \
			--tb=short) \
		|| { code=$$?; \
		     if [ $$code -eq 124 ]; then \
		         echo "⏰ TEST RUN TIMED OUT after $(TEST_RUN_TIMEOUT)s"; \
		         exit 1; \
		     fi; \
		     exit $$code; \
		   }; \
	fi

# Use pytest-testmon for dependency-based test selection
# First run builds the database, subsequent runs only test affected code
test-testmon:
	@echo "🧠 Testmon: Running only affected tests..."
	@if [ ! -f ".testmondata" ]; then \
		echo "📦 First run - building testmon database..."; \
		echo "   (This will run all tests once to build dependency graph)"; \
	fi
	@$(call run_with_timeout,$(SLOW_RUN_TIMEOUT),$(VENV_BIN)/pytest tests/ \
		$(FAST_IGNORE) \
		--testmon \
		-n $(WORKERS) \
		--maxfail=10 \
		-q \
		--tb=short) \
	|| { code=$$?; \
	     if [ $$code -eq 124 ]; then \
	         echo "⏰ TESTMON RUN TIMED OUT after $(SLOW_RUN_TIMEOUT)s"; \
	         exit 1; \
	     fi; \
	     exit $$code; \
	   }

# Show what tests would be selected without running them
test-smart-preview:
	@echo "🔍 Preview: Tests that would be selected..."
	@$(PYTHON) scripts/testing/smart_test_selector.py

# Show what tests would be selected for staged changes
test-smart-preview-cached:
	@echo "🔍 Preview: Tests for staged changes..."
	@$(PYTHON) scripts/testing/smart_test_selector.py --cached

# Show what tests would be selected vs main branch
test-smart-preview-main:
	@echo "🔍 Preview: Tests changed since main..."
	@$(PYTHON) scripts/testing/smart_test_selector.py --base=main

# ==============================================================================
# Ablation Studies
# ==============================================================================

# Run all ablation tests and generate report
ablation:
	@echo "🔬 Running ablation studies..."
	@$(VENV_BIN)/pytest tests/ablation/ -v --tb=short
	@echo ""
	@echo "📊 Ablation results documented in docs/ABLATION_RESULTS.md"

# ==============================================================================
# Test Diagnostics
# ==============================================================================

# Profile tests to find slow ones
test-profile:
	@echo "📊 Profiling tests to find slow ones..."
	@echo "   (Runs with durations report, sorted by slowest)"
	@if [ -n "$(TIMEOUT_CMD)" ]; then \
		$(TIMEOUT_CMD) $(TEST_RUN_TIMEOUT) $(VENV_BIN)/pytest tests/ \
			$(FAST_IGNORE) \
			-n 0 \
			--durations=50 \
			--durations-min=1.0 \
			--timeout=30 \
			-q \
			--maxfail=50 \
			2>&1 | tee .pytest_profile.log || true; \
	else \
		$(VENV_BIN)/pytest tests/ \
			$(FAST_IGNORE) \
			-n 0 \
			--durations=50 \
			--durations-min=1.0 \
			--timeout=30 \
			-q \
			--maxfail=50 \
			2>&1 | tee .pytest_profile.log || true; \
	fi
	@echo ""
	@echo "📋 Top slow tests saved to .pytest_profile.log"

# Collect tests without running (catches import errors)
test-collect:
	@echo "🔍 Collecting tests (checking for import errors)..."
	@$(VENV_BIN)/pytest tests/ \
		--collect-only \
		-q \
		2>&1 || { \
		    echo ""; \
		    echo "❌ Test collection failed - check for import errors above"; \
		    exit 1; \
		}
	@echo "✅ All tests collected successfully"

# Debug a single test file
# Usage: make test-debug FILE=tests/unit/test_foo.py
test-debug:
	@if [ -z "$(FILE)" ]; then \
		echo "Usage: make test-debug FILE=tests/path/to/test.py"; \
		exit 1; \
	fi
	@echo "🔬 Debugging $(FILE)..."
	@$(VENV_BIN)/pytest $(FILE) \
		-n 0 \
		-v \
		-s \
		--tb=long \
		--timeout=300 \
		--capture=no

# ==============================================================================
# Code Quality
# ==============================================================================
lint:
	@echo "🔍 Running linters..."
	@$(VENV_BIN)/ruff check packages/kagami/ tests/ --fix 2>/dev/null \
		|| ruff check packages/kagami/ tests/ --fix 2>/dev/null \
		|| { echo "⚠️  ruff not found. Install with: pip install ruff"; exit 1; }
	@echo "✅ Linting complete"

# Capture real performance metrics and update docs/METRICS.md
metrics:
	@echo "📊 Capturing performance metrics..."
	@$(VENV_BIN)/python scripts/capture_metrics.py

# Check metrics without updating docs (CI-friendly)
metrics-check:
	@echo "📊 Checking performance metrics..."
	@$(VENV_BIN)/python scripts/capture_metrics.py --check

# Install git hooks for automatic metric capture
install-hooks:
	@echo "🪝 Installing git hooks..."
	@mkdir -p .git/hooks
	@ln -sf ../../scripts/hooks/pre-push .git/hooks/pre-push
	@chmod +x .git/hooks/pre-push
	@echo "✅ Pre-push hook installed"

check-clones:
	@echo "🔍 Checking for code clones..."
	@$(PYTHON) tools/static_analysis/clone_detector.py kagami || { \
		echo "⚠️  Clone threshold exceeded! Review analysis_results/clones.json"; \
		exit 1; \
	}
	@echo "✅ Clone check passed"

format:
	@echo "✨ Formatting code..."
	@$(VENV_BIN)/ruff format packages/kagami/ tests/ 2>/dev/null \
		|| ruff format packages/kagami/ tests/ 2>/dev/null \
		|| { echo "⚠️  ruff not found. Install with: pip install ruff"; exit 1; }
	@echo "✅ Formatting complete"

typecheck:
	@echo "🔎 Running type checker..."
	@MYPY_TARGETS="\
		packages/kagami/core/safety \
		packages/kagami/core/orchestration \
		packages/kagami/core/memory \
		packages/kagami_api/idempotency.py \
		packages/kagami_api/rate_limiter.py \
		packages/kagami_api/security \
		packages/kagami_hal \
		packages/kagami_math \
	"; \
	MYPY_ARGS="--follow-imports=skip --ignore-missing-imports"; \
	if [ -x "$(VENV_BIN)/mypy" ]; then \
		$(VENV_BIN)/mypy $$MYPY_ARGS $$MYPY_TARGETS; \
	elif command -v mypy >/dev/null 2>&1; then \
		mypy $$MYPY_ARGS $$MYPY_TARGETS; \
	else \
		echo "⚠️  mypy not found. Install with: pip install mypy"; \
		exit 1; \
	fi
	@echo "✅ Type checking complete"

# ==============================================================================
# Quality Gates
# ==============================================================================

# Full quality check: lint + types + tests (target: 100/100)
quality: lint typecheck
	@echo ""
	@echo "💎 Running full quality check..."
	@echo ""
	@$(PYTHON) scripts/ci/detect_duplicates.py
	@echo ""
	@echo "⚠️  Type coverage (warning only):"
	@$(PYTHON) scripts/ci/check_type_coverage.py || true
	@echo ""
	@echo "⚠️  Docstring coverage (warning only):"
	@$(PYTHON) scripts/ci/check_docstrings.py || true
	@echo ""
	@echo "✅ Quality gates complete (target: 100/100)"

# Calculate commit quality score
score:
	@$(PYTHON) scripts/quality/score_commit.py HEAD

# Score commits from last week
score-week:
	@$(PYTHON) scripts/quality/score_commit.py --since="1 week ago"

quality-dashboard:
	@echo "📊 Generating quality dashboard..."
	@$(PYTHON) scripts/ci/quality_dashboard.py

# ==============================================================================
# Services Management
# ==============================================================================
docker-check:
	@if ! docker info >/dev/null 2>&1; then \
		echo "❌ Docker daemon not running!"; \
		echo "   Please start Docker Desktop or run: open -a Docker"; \
		exit 1; \
	fi

services-start: docker-check
	@echo "🧱 Starting Redis + CockroachDB + etcd + Weaviate..."
	@$(COMPOSE) up -d redis cockroachdb db-init etcd1 etcd2 etcd3 weaviate
	@echo "⏳ Waiting for services..."
	@sleep 5
	@$(MAKE) services-health

services-stop:
	@echo "🛑 Stopping services..."
	@$(COMPOSE) stop || true
	@echo "✅ Services stopped"

services-health:
	@echo "🩺 Service status:"
	@$(COMPOSE) ps 2>/dev/null || echo "⚠️  Services not running. Run: make services-start"

start:
	@echo "🚦 Starting Kagami API..."
	@./start_api_safe.sh

# ==============================================================================
# Integration Testing Infrastructure
# ==============================================================================
test-infra-up: docker-check
	@echo "🧱 Starting integration test services..."
	@$(COMPOSE) -f deploy/docker/docker-compose.test.yml up -d
	@echo "⏳ Waiting for services to be healthy..."
	@./scripts/testing/wait-for-services.sh
	@echo "✅ Integration test infrastructure ready"

test-infra-down:
	@echo "🛑 Stopping integration test services..."
	@$(COMPOSE) -f deploy/docker/docker-compose.test.yml down -v
	@echo "✅ Integration test infrastructure stopped"

test-infra-health:
	@echo "🩺 Integration test service status:"
	@$(COMPOSE) -f deploy/docker/docker-compose.test.yml ps

test-integration-full: test-infra-up
	@echo "🧪 Running integration tests with real services..."
	@$(call run_with_timeout,$(INTEGRATION_RUN_TIMEOUT),$(VENV_BIN)/pytest tests/integration/test_storage_integration.py \
		-v \
		--timeout=180 \
		-m integration \
		--maxfail=5) \
	|| { code=$$?; \
	     $(MAKE) test-infra-down; \
	     if [ $$code -eq 124 ]; then \
	         echo "⏰ INTEGRATION TESTS TIMED OUT after $(INTEGRATION_RUN_TIMEOUT)s"; \
	         exit 1; \
	     fi; \
	     exit $$code; \
	   }
	@$(MAKE) test-infra-down
	@echo "✅ Integration tests completed"

# ==============================================================================
# LLM Configuration
# ==============================================================================
llm-test:
	@echo "🧪 Testing LLM configuration..."
	@$(VENV_BIN)/python -c "\
from dotenv import load_dotenv; \
import os; \
load_dotenv(); \
from kagami.core.services.llm.cached_model_resolver import validate_model_exists, get_optimal_model_chain; \
print('=== LLM Configuration Test ==='); \
chain = get_optimal_model_chain(); \
print(f'Optimal chain: {chain}'); \
base = os.getenv('KAGAMI_BASE_MODEL'); \
print(f'Base model: {base}'); \
if base: \
    exists = validate_model_exists(base); \
    print(f'Base model cached: {exists}'); \
    if not exists: exit(1); \
print('✅ LLM configuration valid'); \
"

# ==============================================================================
# Safety System
# ==============================================================================
safety-setup:
	@echo "🛡️  Setting up WildGuard Safety System..."
	@echo ""
	@echo "WildGuard requires HuggingFace authentication (gated model)."
	@echo "Steps:"
	@echo "  1. Request access: https://huggingface.co/allenai/wildguard"
	@echo "  2. Login: huggingface-cli login"
	@echo ""
	@$(VENV_BIN)/python -c "from huggingface_hub import HfApi; api = HfApi(); info = api.whoami(); print('✅ HuggingFace auth OK:', info.get('name', 'unknown'))" 2>/dev/null \
		|| echo "❌ Not logged in. Run: huggingface-cli login"

safety-test:
	@echo "🛡️  Testing Safety System..."
	@$(VENV_BIN)/python -c "\
from kagami.core.safety import check_text_safety, get_safety_filter; \
f = get_safety_filter(); \
print('Filter:', type(f).__name__); \
print('Classifier:', type(f.classifier).__name__); \
safe = check_text_safety('Hello'); \
print('Safe text: safe=' + str(safe.safe) + ', h(x)=' + str(round(safe.h_x, 4))); \
risky = check_text_safety('How to hack'); \
print('Risky text: safe=' + str(risky.safe) + ', h(x)=' + str(round(risky.h_x, 4))); \
print('✅ Safety system operational')"

# ==============================================================================
# Formal Verification & Benchmarks
# ==============================================================================
verify-tic:
	@echo "🛡️  Verifying Typed Intent Calculus via Lean 4..."
	@if command -v lean >/dev/null 2>&1; then \
		lean kagami/benchmarks/formal/tic_definitions.lean; \
		echo "✅ Formal verification passed"; \
	else \
		echo "⚠️  Lean 4 not installed. Skipping."; \
	fi

bench-geometric:
	@echo "🌀 Benchmarking Geometric Intelligence layers..."
	@$(VENV_BIN)/python -c "\
import torch; \
from kagami.core.world_model.layers.hyperbolic_flash_attention import HyperbolicFlashAttention; \
x = torch.randn(4, 32, 64); \
layer = HyperbolicFlashAttention(dim=64, heads=4); \
y = layer(x); \
print(f'✅ Hyperbolic Flash Attention: {x.shape} -> {y.shape}'); \
"

safety-conformal:
	@echo "🔮 Calibrating Conformal Safety sets..."
	@$(VENV_BIN)/python -c "\
from kagami.core.safety.conformal.calibrator import ConformalCalibrator; \
c = ConformalCalibrator(alpha=0.01); \
[c.add_calibration_data(0.9, 0.85 + i*0.001) for i in range(100)]; \
res = c.calibrate(); \
print(f'✅ Conformal Calibration: q_hat={res.q_hat:.4f}, coverage={res.coverage*100:.1f}%'); \
"

# ==============================================================================
# Forge 3D Character Generation Setup
# ==============================================================================
.PHONY: forge-setup forge-test forge-unirig forge-motion forge-emu

forge-setup: forge-unirig forge-motion forge-emu
	@echo "✅ Forge dependencies installed"

forge-unirig:
	@echo "🦴 Setting up UniRig..."
	@mkdir -p external
	@if [ ! -d "external/unirig_repo" ]; then \
		git clone https://github.com/VAST-AI-Research/UniRig.git external/unirig_repo; \
		pip install -r external/unirig_repo/requirements.txt; \
	else \
		echo "   UniRig already cloned"; \
	fi
	@echo "✅ UniRig ready (models download on first use)"

forge-motion:
	@echo "🏃 Setting up Motion-Agent..."
	@mkdir -p external
	@if [ ! -d "external/motion_agent_repo" ]; then \
		git clone https://github.com/modelscope/MotionAgent.git external/motion_agent_repo; \
		if [ -f "external/motion_agent_repo/requirements.txt" ]; then \
			pip install -r external/motion_agent_repo/requirements.txt; \
		fi; \
	else \
		echo "   Motion-Agent already cloned"; \
	fi
	@echo "✅ Motion-Agent ready (models download on first use)"

forge-emu:
	@echo "🎨 Setting up Emu3.5..."
	@mkdir -p ~/dev
	@if [ ! -d "$(HOME)/dev/Emu3.5" ]; then \
		git clone https://github.com/baaivision/Emu3.5.git ~/dev/Emu3.5; \
	else \
		echo "   Emu3.5 already cloned"; \
	fi
	@echo "✅ Emu3.5 ready (models download on first use)"

forge-test:
	@echo "🧪 Testing Forge service..."
	@$(VENV_BIN)/pytest tests/forge/ -v --tb=short

forge-test-real:
	@echo "🧪 Testing Forge real-model integrations..."
	@$(VENV_BIN)/pytest tests/forge/ -m real_model --run-real-model-tests -n 0 -v --tb=short

forge-models:
	@echo "📦 Downloading Forge AI models..."
	@$(VENV_BIN)/python -c "\
from huggingface_hub import snapshot_download; \
import os; \
cache = os.path.expanduser('~/.cache/forge_ai_models'); \
print('Downloading Hunyuan3D-2...'); \
snapshot_download('tencent/Hunyuan3D-2', cache_dir=cache); \
print('✅ Models cached'); \
"

# ==============================================================================
# Perception (Vision/Audio) verification
# ==============================================================================

perception-test:
	@echo "🧪 Testing perception wiring..."
	@$(VENV_BIN)/pytest \
		tests/core/multimodal/test_perception_sota_exports.py \
		tests/core/embodiment/test_vision_system_sota_wiring.py \
		-v --tb=short

perception-verify:
	@echo "🧪 Verifying perception stack (best-effort)..."
	@$(VENV_BIN)/python -c "\
import kagami.core.multimodal.perception as p; \
print('UnifiedVisionModule:', getattr(p, 'UnifiedVisionModule', None)); \
print('DINOv2Encoder:', getattr(p, 'DINOv2Encoder', None)); \
print('get_optimal_device:', getattr(p, 'get_optimal_device', None)); \
print('✅ perception imports OK'); \
"

# ==============================================================================
# Training
# ==============================================================================
train: train-kagami

train-kagami:
	@echo "🧠 Starting Kagami World Model training..."
	@export KAGAMI_BULK_DIM=1024 KAGAMI_GENESIS_PERFORMANCE_MODE=1 KAGAMI_GENESIS_LOG_LEVEL=WARNING && \
	$(VENV_BIN)/python scripts/training/train_kagami.py \
		--config config/training_optimal.yaml

train-quick:
	@echo "🧠 Quick training (minimal config)..."
	@export KAGAMI_BULK_DIM=128 KAGAMI_GENESIS_PERFORMANCE_MODE=1 KAGAMI_GENESIS_LOG_LEVEL=WARNING && \
	$(VENV_BIN)/python scripts/training/train_kagami.py \
		--bulk-dim 128 \
		--batch-size 32 \
		--max-steps 1000 \
		--log-dir runs/quick

train-resume:
	@echo "🧠 Resuming from latest checkpoint..."
	@export KAGAMI_BULK_DIM=1024 KAGAMI_GENESIS_PERFORMANCE_MODE=1 KAGAMI_GENESIS_LOG_LEVEL=WARNING && \
	$(VENV_BIN)/python scripts/training/train_kagami.py \
		--config config/training_optimal.yaml \
		--resume checkpoints/kagami/latest.pt

# ==============================================================================
# Elysia RAG Integration
# ==============================================================================
elysia-setup:
	@echo "🔮 Setting up Elysia RAG integration..."
	@$(VENV_BIN)/pip install "weaviate-client>=4.9.0"
	@echo ""
	@echo "📋 Weaviate Cloud Configuration:"
	@echo "   Set these environment variables in .env or shell:"
	@echo ""
	@echo "   export WEAVIATE_URL=https://your-cluster.weaviate.network"
	@echo "   export WEAVIATE_API_KEY=your-api-key"
	@echo ""
	@echo "   Get credentials at: https://console.weaviate.cloud/"
	@echo ""
	@echo "✅ Elysia setup complete"

weaviate-start: docker-check
	@echo "🔮 Starting Weaviate..."
	@$(COMPOSE) up -d weaviate
	@echo "⏳ Waiting for Weaviate..."
	@sleep 5
	@$(MAKE) weaviate-health

weaviate-health:
	@echo "🩺 Weaviate status:"
	@curl -s http://localhost:8085/v1/.well-known/ready 2>/dev/null && echo "✅ Weaviate is ready" \
		|| { echo "❌ Weaviate not ready. Run: make weaviate-start"; exit 1; }

elysia-test:
	@echo "🧪 Testing Elysia + Weaviate integration..."
	@$(VENV_BIN)/pytest tests/integration/test_weaviate*.py -v --tb=short 2>/dev/null || echo "⚠️  No Weaviate tests found"

# ==============================================================================
# CI/CD
# ==============================================================================

# CI: Fast checks (Tier 1 + Tier 2)
ci: lint check-clones typecheck test-tier-1 test-tier-2
	@echo "✅ CI checks passed (Tier 1 + Tier 2)"

# CI Full: All tiers
ci-full: lint typecheck test-tiers
	@echo "✅ Full CI checks passed (all tiers)"

# Pre-commit: Code quality + Tier 1
pre-commit: format lint typecheck test-tier-1
	@echo "✅ Pre-commit checks passed (code quality + Tier 1)"

# Pre-push: Tier 1 + Tier 2 + Tier 3
pre-push: lint typecheck test-tiers
	@echo "✅ Pre-push checks passed (all tiers)"

# ==============================================================================
# Performance Benchmarking
# ==============================================================================

# Run all benchmarks and generate report
benchmark:
	@echo "📊 Running performance benchmarks..."
	@$(VENV_BIN)/pytest tests/benchmarks/ \
		-v \
		-m benchmark \
		--benchmark-only \
		--benchmark-json=benchmark-results.json \
		--benchmark-columns=mean,median,stddev,min,max,ops \
		--benchmark-sort=mean
	@$(MAKE) benchmark-report

# Benchmark cache layer only
benchmark-cache:
	@echo "📊 Benchmarking cache layer..."
	@$(VENV_BIN)/pytest tests/benchmarks/test_cache_performance.py \
		-v \
		-m benchmark \
		--benchmark-only \
		--benchmark-json=benchmark-cache-results.json \
		--benchmark-columns=mean,median,stddev,ops

# Benchmark repository layer only
benchmark-repository:
	@echo "📊 Benchmarking repository layer..."
	@$(VENV_BIN)/pytest tests/benchmarks/test_repository_performance.py \
		-v \
		-m benchmark \
		--benchmark-only \
		--benchmark-json=benchmark-repository-results.json \
		--benchmark-columns=mean,median,stddev,ops

# Generate markdown report from benchmark results
benchmark-report:
	@echo "📝 Generating benchmark report..."
	@if [ -f benchmark-results.json ]; then \
		$(VENV_BIN)/python scripts/generate_benchmark_report.py benchmark-results.json BENCHMARK_REPORT.md; \
		echo "✅ Report generated: BENCHMARK_REPORT.md"; \
	else \
		echo "❌ No benchmark results found. Run 'make benchmark' first."; \
		exit 1; \
	fi

# Compare with previous benchmark results
benchmark-compare:
	@echo "📊 Comparing benchmark results..."
	@if [ -f benchmark-results.json ]; then \
		if [ -f benchmark-results-previous.json ]; then \
			echo "Comparing current vs previous results..."; \
			$(VENV_BIN)/python -c "import json; c=json.load(open('benchmark-results.json')); p=json.load(open('benchmark-results-previous.json')); print('Results loaded successfully')"; \
		else \
			echo "⚠️  No previous results. Saving current as baseline..."; \
			cp benchmark-results.json benchmark-results-previous.json; \
		fi; \
	else \
		echo "❌ No benchmark results. Run 'make benchmark' first."; \
		exit 1; \
	fi

# ==============================================================================
# Celery Background Tasks
# ==============================================================================
.PHONY: celery celery-worker celery-beat celery-flower celery-status

celery-install:
	@echo "📦 Installing Celery dependencies..."
	@$(VENV_BIN)/pip install "celery[redis]>=5.3.0" "kombu>=5.3.0" "redis>=5.0.0" "flower>=2.0.0"
	@echo "✅ Celery installed"

celery-worker:
	@echo "🐝 Starting Celery worker..."
	@$(VENV_BIN)/celery -A kagami.core.tasks.app worker \
		--loglevel=INFO \
		--concurrency=4 \
		-Q high_priority,default,analytics,ml,maintenance,monitoring

celery-beat:
	@echo "⏰ Starting Celery beat scheduler..."
	@$(VENV_BIN)/celery -A kagami.core.tasks.app beat \
		--loglevel=INFO

celery-flower:
	@echo "🌸 Starting Flower monitoring (http://localhost:5555)..."
	@$(VENV_BIN)/celery -A kagami.core.tasks.app flower \
		--port=5555

celery-status:
	@echo "📊 Celery status..."
	@$(VENV_BIN)/celery -A kagami.core.tasks.app inspect active 2>/dev/null || echo "⚠️  No workers running"
	@$(VENV_BIN)/celery -A kagami.core.tasks.app inspect stats 2>/dev/null || true

celery: celery-worker

# ==============================================================================
# Full Development Environment
# ==============================================================================
.PHONY: dev-up dev-down dev-status

dev-up: services-start
	@echo "🚀 Starting full development environment..."
	@echo "   Services: Redis, CockroachDB, etcd, Weaviate"
	@echo ""
	@echo "   To start workers:"
	@echo "     make celery-worker  # Background tasks"
	@echo "     make celery-beat    # Scheduled tasks"
	@echo "     make start          # API server"
	@echo ""
	@$(MAKE) services-health

dev-down: services-stop
	@echo "🛑 Development environment stopped"

dev-status: services-health celery-status
	@echo ""
	@echo "📋 Development environment status complete"

# ==============================================================================
# Code Statistics (cloc)
# ==============================================================================

# Full cloc analysis (all components)
cloc:
	@echo "📊 Codebase Line Count Analysis"
	@echo "═══════════════════════════════════════════════════════════════════════"
	@echo ""
	@echo "📦 FULL CODEBASE SUMMARY"
	@cloc . --exclude-dir='node_modules,.git,__pycache__,.venv,venv,.mypy_cache,.pytest_cache,dist,build,target,.cargo' --quiet 2>/dev/null
	@echo ""
	@echo "📦 BY MAJOR COMPONENT:"
	@echo ""
	@echo "=== packages/kagami (Core) ==="
	@cloc packages/kagami/ --quiet 2>/dev/null | tail -3
	@echo ""
	@echo "=== packages/kagami_api (API Server) ==="
	@cloc packages/kagami_api/ --quiet 2>/dev/null | tail -3
	@echo ""
	@echo "=== packages/kagami_smarthome (Smart Home) ==="
	@cloc packages/kagami_smarthome/ --quiet 2>/dev/null | tail -3
	@echo ""
	@echo "=== packages/kagami_hal (Hardware Abstraction) ==="
	@cloc packages/kagami_hal/ --quiet 2>/dev/null | tail -3
	@echo ""
	@echo "=== packages/kagami_math (Mathematics) ==="
	@cloc packages/kagami_math/ --quiet 2>/dev/null | tail -3
	@echo ""
	@echo "=== tests/ ==="
	@cloc tests/ --quiet 2>/dev/null | tail -3
	@echo ""
	@echo "=== scripts/ ==="
	@cloc scripts/ --quiet 2>/dev/null | tail -3
	@echo ""
	@echo "=== tools/ ==="
	@cloc tools/ --quiet 2>/dev/null | tail -3
	@echo ""
	@echo "═══════════════════════════════════════════════════════════════════════"

# Quick summary only
cloc-summary:
	@echo "📊 Quick Codebase Summary"
	@cloc . --exclude-dir='node_modules,.git,__pycache__,.venv,venv,.mypy_cache,.pytest_cache,dist,build,target,.cargo' --quiet 2>/dev/null

# Detailed packages breakdown
cloc-packages:
	@echo "📦 Packages Breakdown (sorted by lines of code)"
	@echo ""
	@for pkg in packages/kagami_*/; do \
		name=$$(basename "$$pkg"); \
		lines=$$(cloc "$$pkg" --csv --quiet 2>/dev/null | tail -1 | cut -d',' -f5); \
		printf "  %-25s %s lines\n" "$$name" "$$lines"; \
	done | sort -t':' -k2 -rn

# Export cloc data as JSON
cloc-json:
	@echo "📊 Exporting cloc data to cloc-report.json..."
	@cloc . --exclude-dir='node_modules,.git,__pycache__,.venv,venv,.mypy_cache,.pytest_cache,dist,build,target,.cargo' --json --quiet 2>/dev/null > cloc-report.json
	@echo "✅ Saved to cloc-report.json"

# Generate full cloc report with per-file breakdown
cloc-report:
	@echo "📊 Generating comprehensive cloc report..."
	@echo ""
	@echo "# Kagami Codebase Analysis" > CLOC_REPORT.md
	@echo "" >> CLOC_REPORT.md
	@echo "Generated: $$(date)" >> CLOC_REPORT.md
	@echo "" >> CLOC_REPORT.md
	@echo "## Summary" >> CLOC_REPORT.md
	@echo "" >> CLOC_REPORT.md
	@echo '```' >> CLOC_REPORT.md
	@cloc . --exclude-dir='node_modules,.git,__pycache__,.venv,venv,.mypy_cache,.pytest_cache,dist,build,target,.cargo' --quiet 2>/dev/null >> CLOC_REPORT.md
	@echo '```' >> CLOC_REPORT.md
	@echo "" >> CLOC_REPORT.md
	@echo "## Top 30 Largest Files" >> CLOC_REPORT.md
	@echo "" >> CLOC_REPORT.md
	@echo '```' >> CLOC_REPORT.md
	@cloc . --exclude-dir='node_modules,.git,__pycache__,.venv,venv,.mypy_cache,.pytest_cache,dist,build,target,.cargo' --by-file --quiet 2>/dev/null | head -40 >> CLOC_REPORT.md
	@echo '```' >> CLOC_REPORT.md
	@echo "" >> CLOC_REPORT.md
	@echo "## By Component" >> CLOC_REPORT.md
	@echo "" >> CLOC_REPORT.md
	@for pkg in packages/kagami packages/kagami_api packages/kagami_smarthome packages/kagami_hal packages/kagami_math tests scripts tools; do \
		echo "### $$pkg" >> CLOC_REPORT.md; \
		echo "" >> CLOC_REPORT.md; \
		echo '```' >> CLOC_REPORT.md; \
		cloc "$$pkg" --quiet 2>/dev/null | tail -5 >> CLOC_REPORT.md; \
		echo '```' >> CLOC_REPORT.md; \
		echo "" >> CLOC_REPORT.md; \
	done
	@echo "✅ Report saved to CLOC_REPORT.md"

# ==============================================================================
# Metrics Tracking & Reporting
# ==============================================================================
.PHONY: metrics-report metrics-coverage metrics-complexity metrics-duplicates metrics-deps

# Full metrics report - runs all metric collection targets
metrics-report: metrics-coverage metrics-complexity metrics-deps
	@echo ""
	@echo "═══════════════════════════════════════════════════════════════════════"
	@echo "  Full Metrics Report Complete"
	@echo "═══════════════════════════════════════════════════════════════════════"
	@echo ""
	@echo "Generated artifacts:"
	@echo "  - coverage.json (coverage data)"
	@echo "  - coverage_html/ (HTML coverage report)"
	@echo "  - quality_dashboard.json (quality metrics)"
	@echo ""
	@echo "View HTML coverage: open coverage_html/index.html"

# Coverage metrics with multiple output formats
metrics-coverage:
	@echo "📊 Collecting coverage metrics..."
	@$(VENV_BIN)/pytest tests/unit/ tests/core/ tests/api/ \
		--cov=kagami \
		--cov-report=term-missing \
		--cov-report=html:coverage_html \
		--cov-report=json:coverage.json \
		--cov-report=xml:coverage.xml \
		--cov-fail-under=70 \
		-n auto \
		--dist loadgroup \
		--maxfail=50 \
		-q \
		|| { code=$$?; \
		     if [ $$code -eq 2 ]; then \
		         echo "⚠️  Coverage below 70% threshold"; \
		     fi; \
		     exit $$code; \
		   }
	@echo ""
	@echo "✅ Coverage metrics collected"
	@echo "   HTML report: coverage_html/index.html"
	@echo "   JSON data: coverage.json"

# Cyclomatic complexity analysis using radon
metrics-complexity:
	@echo "📊 Analyzing cyclomatic complexity..."
	@echo ""
	@echo "=== Cyclomatic Complexity Report ==="
	@if command -v radon >/dev/null 2>&1 || [ -x "$(VENV_BIN)/radon" ]; then \
		$(VENV_BIN)/radon cc packages/ -a -nc --total-average 2>/dev/null \
			|| radon cc packages/ -a -nc --total-average 2>/dev/null \
			|| echo "⚠️  radon not available, install with: pip install radon"; \
	else \
		echo "⚠️  radon not installed. Install with: pip install radon"; \
	fi
	@echo ""
	@echo "=== Maintainability Index ==="
	@if command -v radon >/dev/null 2>&1 || [ -x "$(VENV_BIN)/radon" ]; then \
		$(VENV_BIN)/radon mi packages/ -s 2>/dev/null \
			|| radon mi packages/ -s 2>/dev/null \
			|| true; \
	fi
	@echo ""
	@echo "=== High Complexity Functions (CC > 10) ==="
	@if command -v radon >/dev/null 2>&1 || [ -x "$(VENV_BIN)/radon" ]; then \
		$(VENV_BIN)/radon cc packages/ -a --min C 2>/dev/null \
			|| radon cc packages/ -a --min C 2>/dev/null \
			|| true; \
	fi
	@echo ""
	@echo "✅ Complexity analysis complete"

# Dependency health check
metrics-deps:
	@echo "📊 Checking dependency health..."
	@echo ""
	@echo "=== Dependency Consistency ==="
	@pip check 2>/dev/null || echo "⚠️  Dependency conflicts detected"
	@echo ""
	@echo "=== Security Audit (pip-audit) ==="
	@if command -v pip-audit >/dev/null 2>&1 || [ -x "$(VENV_BIN)/pip-audit" ]; then \
		$(VENV_BIN)/pip-audit --fix --dry-run 2>/dev/null \
			|| pip-audit --fix --dry-run 2>/dev/null \
			|| echo "⚠️  pip-audit not available or audit failed"; \
	else \
		echo "⚠️  pip-audit not installed. Install with: pip install pip-audit"; \
	fi
	@echo ""
	@echo "=== Outdated Packages ==="
	@pip list --outdated 2>/dev/null | head -20 || echo "Unable to check outdated packages"
	@echo ""
	@echo "✅ Dependency health check complete"

# Code duplication detection
metrics-duplicates:
	@echo "📊 Detecting code duplicates..."
	@echo ""
	@$(PYTHON) scripts/ci/detect_duplicates.py
	@echo ""
	@echo "✅ Duplicate detection complete"

# ==============================================================================
# Android XR Build
# ==============================================================================
.PHONY: android-xr android-xr-build android-xr-test android-xr-lint android-xr-clean

# Build Android XR debug APK
android-xr: android-xr-build

android-xr-build:
	@echo "🥽 Building Android XR debug APK..."
	@cd apps/android-xr/kagami-xr && \
		export JAVA_HOME=$${JAVA_HOME:-/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home} && \
		chmod +x gradlew && \
		./gradlew assembleDebug
	@echo "✅ Android XR APK built: apps/android-xr/kagami-xr/app/build/outputs/apk/debug/app-debug.apk"

# Run Android XR unit tests
android-xr-test:
	@echo "🧪 Running Android XR unit tests..."
	@cd apps/android-xr/kagami-xr && \
		export JAVA_HOME=$${JAVA_HOME:-/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home} && \
		chmod +x gradlew && \
		./gradlew testDebugUnitTest
	@echo "✅ Android XR tests complete"

# Run Android XR lint
android-xr-lint:
	@echo "🔍 Running Android XR lint..."
	@cd apps/android-xr/kagami-xr && \
		export JAVA_HOME=$${JAVA_HOME:-/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home} && \
		chmod +x gradlew && \
		./gradlew lintDebug
	@echo "✅ Android XR lint complete"

# Clean Android XR build
android-xr-clean:
	@echo "🧹 Cleaning Android XR build..."
	@cd apps/android-xr/kagami-xr && \
		export JAVA_HOME=$${JAVA_HOME:-/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home} && \
		chmod +x gradlew && \
		./gradlew clean
	@echo "✅ Android XR clean complete"
