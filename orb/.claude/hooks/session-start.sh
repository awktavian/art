#!/bin/bash
# KagamiOS Session Start — Optimized
# Sets test environment and validates readiness

export KAGAMI_TEST_MODE=1
export KAGAMI_ENV=test
export PYTEST_RUNNING=1
export KAGAMI_DISABLE_VLLM=1
export KAGAMI_TEST_DISABLE_REDIS=1
export KAGAMI_DISABLE_ETCD=1
export KAGAMI_LOAD_WORLD_MODEL=0
export TRANSFORMERS_VERBOSITY=error

# Quick validation (silent unless error)
[ -d ".venv" ] && source .venv/bin/activate 2>/dev/null

# Ready
echo "鏡 Ready"
