# Vulture Whitelist
# This file contains references to code that Vulture incorrectly flags as dead.
# Vulture sees these usages and knows they are "used".

import kagami_api.lifespan_v2
import kagami.boot.actions

# Lifespan and Boot Actions are used by FastAPI/Uvicorn via string reference
_ = kagami_api.lifespan_v2.lifespan_v2
_ = kagami.boot.actions.startup_database
_ = kagami.boot.actions.startup_redis
_ = kagami.boot.actions.startup_etcd
_ = kagami.boot.actions.shutdown_etcd
_ = kagami.boot.actions.startup_hal
_ = kagami.boot.actions.startup_ambient_os
_ = kagami.boot.actions.startup_orchestrator
_ = kagami.boot.actions.startup_brain
_ = kagami.boot.actions.startup_background_tasks
_ = kagami.boot.actions.startup_socketio
_ = kagami.boot.actions.startup_feature_flags
_ = kagami.boot.actions.shutdown_all
_ = kagami.boot.actions.enforce_full_operation_check

# API Settings often flagged as unused
from kagami_api.api_settings import (
    IDEMPOTENCY_CACHE_TTL_SECONDS,
    IDEMPOTENCY_PERSIST_TTL_MINUTES,
)

_ = IDEMPOTENCY_CACHE_TTL_SECONDS
_ = IDEMPOTENCY_PERSIST_TTL_MINUTES

# Common Pydantic/FastAPI false positives
# (Add specific model fields here if they persist)

# API parameters documented for future use (not dead code)
# gsm8k_runner.py:335 - use_orchestrator is a documented future enhancement
# genetic_algorithm.py:18 - crossover_rate documented as "not used in current simple GA"
# emu_image_generator.py:113 - num_inference_steps documented as "unused - Emu uses DiDA"

# TYPE_CHECKING imports (not dead code)
# llm_mixin.py:17 - LLMService is used for type hints in TYPE_CHECKING block

# Protocol/interface method parameters (not dead code)
# crdt_sync.py:26 - peer_state is a stub method parameter for future impl
