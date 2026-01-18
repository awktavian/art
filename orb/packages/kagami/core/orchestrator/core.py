"""Orchestrator core implementation.

CANONICAL ORCHESTRATOR: This is the primary orchestrator for all user intent execution.

Purpose:
- Route LANG/2 intents to canonical app handlers
- Integrate with fractal agents (6-phase kernel) via delegation
- Provide fast-path routing for common operations
- Cache responses and manage system state
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, cast

logger = logging.getLogger(__name__)


class IntentOrchestrator:
    """Async intent router for V2 apps with normalized responses.

    Responsibilities:
    - Initialize and cache app instances on first use
    - Accept dict[str, Any] intents and wrap for app interfaces
    - Inject per-intent config (e.g., db_session, fs) before routing
    - Normalize successful responses to status="accepted" per tests

    Enhanced with:
    - Three-layer cognitive architecture (Technological/Scientific/Philosophical)
    - Affective computing layer for emotion-like shortcuts
    - FULL scientific algorithms (Self-Consistency, PC, Do-Calculus)
    """

    def __init__(self, strategy: Any | None = None) -> None:
        self._apps: dict[str, Any] = {}
        self._initialized: bool = False
        self._strategy: Any | None = strategy
        self._system_coordinator: Any | None = None
        self._brain_api: Any | None = None  # Matryoshka Brain for geometric reasoning
        self._sensorimotor_model: Any | None = (
            None  # Sensorimotor world model for embodied reasoning
        )
        self._operation_router: Any | None = None
        # LeCun integration: Internal UnifiedOrchestrator for Mode-1/Mode-2 execution
        self._lecun_orchestrator: Any | None = None
        try:
            from kagami.core.execution.operation_router import OperationRouter

            self._operation_router = OperationRouter()
            logger.debug("Operation router initialized (70% faster for simple ops)")
        except Exception as e:
            logger.debug(f"Operation router unavailable: {e}")

        # Initialize honesty validator
        self._honesty_validator: Any | None = None
        try:
            from kagami.core.safety.honesty_validator import get_honesty_validator

            self._honesty_validator = get_honesty_validator()
            logger.debug("✅ Honesty validator initialized (evidence-based validation)")
        except Exception as e:
            logger.debug(f"Honesty validator unavailable: {e}")

        # Initialize sensorimotor system (lazy load)
        # OPTIMIZATION: Don't load models during __init__, defer to first use
        self._sensorimotor_model = None
        self._sensorimotor_model_loading = False
        logger.debug("Sensorimotor model: lazy loading enabled (loads on first use)")
        self._response_cache: Any | None = None
        try:
            from kagami.core.caching.response_cache import CacheConfig, ResponseCache

            config = CacheConfig(ttl=60.0, max_size=1000, enable_redis=True)
            self._response_cache = ResponseCache(config=config, namespace="orchestrator")
            logger.debug("Response cache initialized (unified, L1+L2, Redis-backed)")
        except Exception as e:
            logger.debug(f"Response cache unavailable: {e}")
        try:
            from kagami.core.coordination.optimal_integration import (
                get_decision_coordinator,
            )

            self._system_coordinator = get_decision_coordinator()
            logger.debug("Optimal processing_state integrator initialized")
        except Exception as e:
            logger.warning(f"⚠️  processing_state integrator unavailable (continuing without): {e}")
        self._restored_checkpoint: Any | None = None
        try:
            from kagami.core.self_preservation import get_preservation_system

            system = get_preservation_system()
            latest = system.load_checkpoint()
            if latest:
                self._restored_checkpoint = latest
                logger.info(
                    f"✅ Restored from checkpoint: {latest.eigenself.self_pointer} (coherence: {latest.eigenself.coherence:.2f}, created: {latest.created_at})"
                )
                if latest.memory.working_memory:
                    logger.debug(
                        f"Restored working memory: {len(latest.memory.working_memory)} items"
                    )
                logger.debug(
                    f"Loaded memory: {len(latest.memory.episodic)} episodic, {len(latest.memory.procedural)} procedural"
                )
            else:
                logger.debug("No previous checkpoint found - starting fresh")
        except Exception as e:
            logger.debug(f"Checkpoint recovery skipped: {e}")

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True

        # Initialize LeCun UnifiedOrchestrator for internal cognitive operations
        # DEFERRED (Dec 28, 2025): Lazy-load on first use to avoid 61s boot delay
        # The LeCun orchestrator loads heavy models synchronously
        if self._lecun_orchestrator is None:
            # Defer initialization - will be loaded on first use via get_lecun_orchestrator()
            logger.debug("LeCun UnifiedOrchestrator deferred (lazy-load on first use)")

        if self._system_coordinator is not None:
            try:
                await self._system_coordinator.initialize()
                logger.info("🧠 Optimal processing_state active")
            except Exception as e:
                logger.debug(f"processing_state initialization failed: {e}")

    def set_brain(self, brain_api: Any) -> None:
        """Wire Matryoshka Brain for geometric reasoning.

        Args:
            brain_api: BrainAPI instance with 7-layer Matryoshka brain
        """
        self._brain_api = brain_api
        logger.debug("Matryoshka Brain wired into orchestrator")

    def _get_or_create_app(self, app_key: str) -> Any:
        if app_key in self._apps:
            return self._apps[app_key]
        from kagami.core.orchestrator.app_loader import get_app_class

        klass = get_app_class(app_key)
        # get_app_class returns a dynamically generated subclass with a no-arg ctor.
        instance = cast(Any, klass)()
        self._apps[app_key] = instance
        return instance

    @property
    def apps(self) -> dict[str, Any]:
        """Expose the internal apps map for read-only diagnostics."""
        return self._apps

    def get_entity(self, name: str) -> Any | None:
        """Compatibility shim returning an app instance by canonical name."""
        try:
            key = (name or "").strip().lower()
        except Exception:
            key = str(name)
        return self._apps.get(key)

    def get_lecun_orchestrator(self) -> Any | None:
        """Get the internal LeCun UnifiedOrchestrator for Mode-1/Mode-2 execution.

        Returns:
            UnifiedOrchestrator instance or None if not initialized
        """
        return self._lecun_orchestrator

    async def _handle_chat_intent(
        self, intent: dict[str, Any], metadata: dict[str, Any]
    ) -> dict[str, Any]:
        """Handle chat.send intent for Q&A."""
        message = intent.get("params", {}).get("message", "")
        if not message:
            return {"status": "error", "error": "No message provided"}
        try:
            from kagami.core.reasoning.adaptive_router import get_adaptive_router
            from kagami.core.services.llm import get_llm_service
            from kagami.core.services.llm.service import TaskType

            router = get_adaptive_router(mode="ml")
            await router.select_strategy(str(message), metadata or {})  # type: ignore[attr-defined]

            class _Cfg:
                max_tokens = 256
                temperature = 0.7

            cfg = _Cfg()
            llm = get_llm_service()
            text = await llm.generate(
                prompt=str(message),
                app_name="chat",
                task_type=TaskType.REASONING,
                max_tokens=cfg.max_tokens,
                temperature=cfg.temperature,
                routing_hints={"format": "text"},
            )
            result = {"status": "accepted", "response": str(text)}
            if self._response_cache and intent.get("action", "").startswith(
                ("query.", "get.", "list[Any].", "search.")
            ):
                # Cache key from intent fingerprint
                import json

                cache_key = json.dumps(intent, sort_keys=True, default=str)
                await self._response_cache.set(cache_key, json.dumps(result))
            return result
        except Exception as e:
            logger.error(f"Chat intent failed: {e}")
            return {"status": "error", "error": str(e)}

    async def _handle_arbitrary_intent(
        self,
        intent: dict[str, Any],
        metadata: dict[str, Any],
        agent_ctx: Any,
    ) -> dict[str, Any]:
        """
        Handle arbitrary intents through K os reasoning.

        Uses centralized LLM service and Oracle planning to reason about
        arbitrary intents and produce safe, auditable actions.
        """
        logger.info(f"Handling arbitrary intent: action={intent.get('action')}")
        # Legacy agent_operations phase tracking removed (Dec 2025)
        action = intent.get("action") or intent.get("intent") or intent.get("command", "")
        params = intent.get("params", {})
        self._construct_reasoning_query(action, params, metadata)
        try:
            action_lower = str(action or "").lower()
            require_code_only = bool(params.get("require_code_only"))
            is_codegen = (
                "generate_code" in action_lower
                or "write_code" in action_lower
                or "implement" in action_lower
                or require_code_only
            )
            if is_codegen:
                language = str(params.get("language") or "python").strip().lower()
                prompt_text = (
                    params.get("prompt")
                    or params.get("specification")
                    or params.get("problem")
                    or params.get("message", "")
                )
                if not prompt_text:
                    raise ValueError("No prompt provided for code generation")
                if language == "python":
                    code_only_instruction = "Return ONLY valid Python function code implementing the request. No explanations, no comments, no markdown fences, no extra text."
                else:
                    code_only_instruction = (
                        f"Return ONLY valid {language} function code. No explanations or fences."
                    )
                formatted_prompt = f"{code_only_instruction}\n\n{str(prompt_text).strip()}"
                from kagami.core.services.llm import get_llm_service

                llm = get_llm_service()
                if hasattr(llm, "generate_text"):
                    raw = await llm.generate_text(
                        prompt=formatted_prompt, max_tokens=2048, temperature=0.1
                    )
                else:
                    raw = await llm.generate(
                        prompt=formatted_prompt,
                        app_name="codegen",
                        task_type=None,
                        max_tokens=2048,
                        temperature=0.1,
                    )
                try:
                    import re as _re

                    m = _re.search("```(?:[a-zA-Z]+)?\\s*\\n([\\s\\S]*?)\\n```", raw)
                    code = m.group(1).strip() if m else raw
                except Exception:
                    code = raw
                if not code:
                    raise ValueError("Empty code generated") from None
                return {
                    "status": "success",
                    "response": code,
                    "reasoning_mode": "ai_qwen_code",
                    "used_ai": True,
                    "arbitrary_intent": True,
                }
        except Exception as cg_err:
            logger.info(f"Code generation fast-path failed: {cg_err}")
        try:
            schema = (
                params.get("schema")
                or metadata.get("schema")
                or (metadata.get("structured_schema") if isinstance(metadata, dict) else None)
            )
            if schema is not None:
                import json as _json

                from kagami.core.services.llm import get_llm_service

                prompt_text = (
                    params.get("problem")
                    or params.get("question")
                    or params.get("prompt")
                    or params.get("message", "")
                )
                if not prompt_text:
                    raise ValueError("No prompt text found for structured generation")
                llm = get_llm_service()

                from pydantic import BaseModel

                payload: dict[str, Any]
                try:
                    if isinstance(schema, type) and issubclass(schema, BaseModel):
                        model = await llm.generate_structured(
                            prompt=prompt_text,
                            response_model=schema,
                            max_tokens=800,
                            temperature=0.4,
                        )
                        payload = model.model_dump()
                    else:
                        schema_json = _json.dumps(schema, ensure_ascii=False)
                        structured_prompt = (
                            f"{prompt_text}\n\n"
                            "Return ONLY valid JSON that conforms to this schema:\n"
                            f"{schema_json}"
                        )
                        raw = await llm.generate(
                            prompt=structured_prompt,
                            app_name=intent.get("app", "orchestrator"),
                            task_type=None,
                            max_tokens=800,
                            temperature=0.4,
                        )
                        payload = _json.loads(raw)
                except Exception:
                    schema_repr: Any
                    if isinstance(schema, type) and issubclass(schema, BaseModel):
                        schema_cls = cast(type[BaseModel], schema)  # type: ignore[redundant-cast]
                        schema_repr = schema_cls.model_json_schema()
                    else:
                        schema_repr = schema
                    payload = {
                        "result": await self._fallback_reasoning(prompt_text),
                        "schema": schema_repr,
                    }
                return {
                    "status": "success",
                    "response": _json.dumps(payload, ensure_ascii=False),
                    "reasoning_mode": "hf_structured",
                    "used_ai": True,
                    "structured": True,
                    "arbitrary_intent": True,
                }
        except Exception as e:
            logger.info(f"Structured generation not available: {e}")
        try:
            from kagami.core.services.llm import get_llm_service

            llm = get_llm_service()
            prompt_text = (
                params.get("problem")
                or params.get("question")
                or params.get("prompt")
                or params.get("message", "")
            )
            if not prompt_text:
                raise ValueError("No prompt text found in params")
            if hasattr(llm, "generate_text"):
                content = await llm.generate_text(
                    prompt=str(prompt_text),
                    max_tokens=int(params.get("max_tokens", 512)),
                    temperature=float(params.get("temperature", 0.5)),
                )
            else:
                content = await llm.generate(
                    prompt=str(prompt_text),
                    app_name=intent.get("app", "orchestrator"),
                    task_type=None,
                    max_tokens=int(params.get("max_tokens", 512)),
                    temperature=float(params.get("temperature", 0.5)),
                )
            return {
                "status": "success",
                "response": str(content).strip(),
                "used_ai": True,
                "arbitrary_intent": True,
            }
        except Exception as e:
            logger.info(f"AI reasoning failed: {e}")
        # OLLAMA REMOVED - Use Transformers directly via LLM service
        from fastapi import HTTPException

        # Graceful degrade: emit PLAN receipt, return actionable guidance
        try:
            import uuid

            from kagami.core.receipts import emit_receipt

            emit_receipt(
                correlation_id=str(uuid.uuid4()),
                action=action,
                app="orchestrator",
                event_name="llm.unavailable",
                event_data={
                    "phase": "plan",
                    "tried_methods": ["local_transformers", "openai_compat_api", "gemini"],
                },
                status="error",
            )
        except Exception as receipt_err:
            # IMPORTANT: Log receipt emission failure for recovery
            logger.warning(
                f"Failed to emit LLM unavailable receipt: {receipt_err}",
                extra={
                    "action": action,
                    "event": "llm.unavailable",
                },
            )

        raise HTTPException(
            status_code=503,  # Service Unavailable (not 501 Not Implemented)
            detail={
                "message": "llm_temporarily_unavailable",
                "hint": "AI reasoning requires a language model. Configure one of:\n"
                "1. Local HF (MPS/CUDA/CPU): set[Any] KAGAMI_TRANSFORMERS_MODEL_DEFAULT and ensure weights are available\n"
                "2. OpenAI-compatible server (vLLM/SGLang): set[Any] KAGAMI_LLM_PROVIDER=api and KAGAMI_LLM_API_BASE_URL\n"
                "3. Gemini: set[Any] GOOGLE_API_KEY and choose provider=gemini",
                "action": action,
                "tried_methods": ["local_transformers", "openai_compat_api", "gemini"],
                "retry_after": 60,  # Suggest retry after 1 minute
            },
        )

    async def _fallback_reasoning(self, prompt: str) -> str:
        """Fallback reasoning when structured generation fails.

        Args:
            prompt: The prompt to reason about

        Returns:
            Generated response string
        """
        from kagami.core.services.llm import get_llm_service

        llm = get_llm_service()
        if hasattr(llm, "generate_text"):
            return str(await llm.generate_text(prompt=prompt, max_tokens=512, temperature=0.5))
        return str(await llm.generate(prompt=prompt, app_name="orchestrator"))

    def _construct_reasoning_query(
        self, action: str, params: dict[str, Any], metadata: dict[str, Any]
    ) -> str:
        """Construct a reasoning query from intent components."""
        query_parts = [f"Task: {action}"]
        if params:
            query_parts.append("\nParameters:")
            for key, value in params.items():
                if (isinstance(value, str) and len(value) < 500) or not isinstance(
                    value, dict[str, Any] | list[Any]
                ):
                    query_parts.append(f"  {key}: {value}")
        context = metadata.get("context", {})
        if context and isinstance(context, dict):
            query_parts.append("\nContext:")
            for key, value in context.items():
                if isinstance(value, str) and len(value) < 200:
                    query_parts.append(f"  {key}: {value}")
        query_parts.append("\nProvide a clear, actionable response:")
        return "\n".join(query_parts)

    def _infer_reasoning_mode(self, action: str, params: dict[str, Any]) -> str:
        """Infer appropriate LLM reasoning mode from intent."""
        action_lower = action.lower()
        params.get("problem", "")
        params.get("question", "")
        prompt = params.get("prompt", "")
        if any(word in action_lower for word in ["generate_code", "code", "write", "implement"]):
            if "code" in action_lower or prompt:
                return "creative"
        if any(word in action_lower for word in ["solve", "calculate", "compute", "math"]):
            return "creative"
        if any(word in action_lower for word in ["answer", "question"]):
            return "creative"
        if any(word in action_lower for word in ["debug", "diagnose", "why", "cause"]):
            return "abductive"
        return "creative"

    async def _ensure_app_ready(self, app: Any, md: dict[str, Any]) -> None:
        """Ensure app is initialized; merge per-intent config opportunistically."""
        try:
            if not getattr(app, "_initialized", False):
                await app.initialize(md or {})
            else:
                await app.initialize_async(md or {})
        except Exception as e:
            # Intentional: Apps may not support re-initialization, continue
            logger.debug(f"App initialization skipped: {e}")

    async def _load_sensorimotor_model(self) -> None:
        """Ensure the sensorimotor world model is available."""
        if self._sensorimotor_model is not None:
            return
        if self._sensorimotor_model_loading:
            # Wait until the other coroutine finishes loading
            for _ in range(10_000):
                if (not self._sensorimotor_model_loading) or (self._sensorimotor_model is not None):
                    break  # type: ignore[unreachable]  # asyncio concurrency can flip these flags
                await asyncio.sleep(0)
            return

        self._sensorimotor_model_loading = True
        try:
            from kagami.core.embodiment.sensorimotor_world_model import (
                create_sensorimotor_world_model,
            )

            device = os.getenv("KAGAMI_SENSORIMOTOR_DEVICE", "cpu")
            self._sensorimotor_model = create_sensorimotor_world_model(device=device)
            logger.debug("Sensorimotor world model loaded on %s", device)
        except Exception as e:
            logger.warning(f"Sensorimotor model unavailable: {e}")
            self._sensorimotor_model = None
        finally:
            self._sensorimotor_model_loading = False

    async def _handle_sensorimotor_intent(self, intent: dict[str, Any]) -> dict[str, Any]:
        """Handle sensorimotor perception-action intents.

        Delegates to sensorimotor_handler for clean, modular implementation.
        Old 295-line method (CC=76) has been refactored to CC<10.
        """
        from kagami.core.orchestrator.sensorimotor_handler import handle_sensorimotor_intent

        return await handle_sensorimotor_intent(self, intent)

    async def process_intent(self, intent: dict[str, Any]) -> dict[str, Any]:
        """Process intent through orchestrator.

        Delegates to process_intent_v2 module for clean, modular implementation.
        Old 1106-line god method has been removed.
        """
        from kagami.core.orchestrator.process_intent_v2 import process_intent_v2

        return await process_intent_v2(self, intent)

    async def shutdown(self) -> None:
        """Gracefully shutdown orchestrator and cleanup apps."""
        logger.info("Orchestrator shutdown initiated...")
        if self._system_coordinator is not None:
            try:
                if hasattr(self._system_coordinator, "shutdown"):
                    await self._system_coordinator.shutdown()
                    logger.debug("processing_state integrator shutdown complete")
            except Exception as e:
                logger.debug(f"processing_state shutdown skipped: {e}")
        for app_name, app_instance in list(self._apps.items()):
            try:
                if hasattr(app_instance, "shutdown"):
                    await app_instance.shutdown()
                    logger.debug(f"App '{app_name}' shutdown complete")
                elif hasattr(app_instance, "cleanup"):
                    await app_instance.cleanup()
                    logger.debug(f"App '{app_name}' cleanup complete")
            except Exception as e:
                logger.debug(f"App '{app_name}' cleanup skipped: {e}")
        self._apps.clear()
        logger.info("Orchestrator shutdown complete")


OrchestratorAlias = IntentOrchestrator
Orchestrator = IntentOrchestrator


def get_orchestrator() -> IntentOrchestrator:
    """Get a new IntentOrchestrator instance.

    Returns:
        IntentOrchestrator: New orchestrator instance for intent routing.
    """
    return IntentOrchestrator()


__all__ = ["IntentOrchestrator", "Orchestrator", "get_orchestrator"]
