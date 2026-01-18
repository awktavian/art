"""Local Inference API - Health probes and model management.

Canonical LLM stack:
- Local inference: HuggingFace Transformers (MPS/CUDA/CPU)
- Remote inference: OpenAI-compatible HTTP (vLLM/SGLang/etc.) via provider="api"
"""

import logging
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from kagami.core.safety import enforce_tier1
from pydantic import BaseModel, Field

from kagami_api.rbac import Permission, require_permission
from kagami_api.response_schemas import get_error_responses

try:
    from kagami.observability.metrics import REGISTRY
    from prometheus_client import Gauge

    _LOCAL_INF_MS: Any = Gauge(
        "kagami_local_inference_probe_ms",
        "Latency in milliseconds for tiny local inference probe",
        ["backend"],
        registry=REGISTRY,
    )
except Exception:
    _LOCAL_INF_MS = None


def get_router() -> APIRouter:
    """Create and configure the API router.

    Factory function for lazy router instantiation.
    Router is not created until this function is called.
    """
    router = APIRouter(prefix="/api/inference", tags=["inference"])
    logger = logging.getLogger(__name__)

    # =============================================================================
    # REQUEST/RESPONSE MODELS
    # =============================================================================

    class ProbeRequest(BaseModel):
        """Request for local inference probe."""

        prompt: str = Field(
            default="ok",
            max_length=100,
            description="Short prompt to probe. Defaults to tiny token budget.",
        )
        budget_ms: int = Field(default=300, ge=50, le=2000, description="Timeout budget in ms")
        use_tiny: bool = Field(default=True, description="Use smallest available model")
        backend: str | None = Field(
            default=None, description="Preferred backend: transformers, api, auto"
        )

    class ProbeResponse(BaseModel):
        """Response from inference probe."""

        status: str = Field(description="Probe status: ok, slow, failed")
        latency_ms: float = Field(description="Actual latency in milliseconds")
        backend: str = Field(description="Backend used")
        model: str | None = Field(description="Model used for probe")
        output: str | None = Field(default=None, description="Model output if any")

    class GenerateRequest(BaseModel):
        """Request for local text generation."""

        prompt: str = Field(..., max_length=4096, description="Input prompt")
        max_tokens: int = Field(
            default=256, ge=1, le=2048, description="Maximum tokens to generate"
        )
        temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Sampling temperature")
        top_p: float = Field(default=0.9, ge=0.0, le=1.0, description="Nucleus sampling")
        stop: list[str] | None = Field(default=None, description="Stop sequences")
        model: str | None = Field(default=None, description="Specific model to use")

    class GenerateResponse(BaseModel):
        """Response from text generation."""

        text: str = Field(description="Generated text")
        tokens_generated: int = Field(description="Number of tokens generated")
        latency_ms: float = Field(description="Generation latency in ms")
        model: str = Field(description="Model used")
        finish_reason: str = Field(description="Reason generation stopped: length, stop, eos")

    class ModelInfo(BaseModel):
        """Information about an available model."""

        name: str = Field(description="Model name/identifier")
        backend: str = Field(description="Backend: transformers, api, etc.")
        size_gb: float | None = Field(default=None, description="Model size in GB")
        loaded: bool = Field(description="Whether model is currently loaded")
        capabilities: list[str] = Field(default_factory=list, description="Model capabilities")

    class ModelsResponse(BaseModel):
        """List of available models."""

        models: list[ModelInfo] = Field(description="Available models")
        default_model: str | None = Field(description="Default model for inference")

    # =============================================================================
    # HELPER FUNCTIONS
    # =============================================================================

    def _probe_model_name(use_tiny: bool) -> str:
        """Select a small model for probes (may download unless offline/cached-only)."""
        import os

        if use_tiny:
            return (
                os.getenv("KAGAMI_INFERENCE_PROBE_MODEL")
                or os.getenv("KAGAMI_TRANSFORMERS_MODEL_FAST")
                or os.getenv("KAGAMI_TRANSFORMERS_MODEL_DEFAULT")
                or "sshleifer/tiny-gpt2"
            )
        return (
            os.getenv("KAGAMI_TRANSFORMERS_MODEL_DEFAULT")
            or os.getenv("KAGAMI_BASE_MODEL")
            or "Qwen/Qwen2.5-14B-Instruct"
        )

    async def _probe_transformers(prompt: str, budget_ms: int) -> tuple[bool, float, str | None]:
        """Probe Transformers backend."""
        try:
            import asyncio

            from kagami.core.services.llm import get_llm_service

            llm = get_llm_service()
            model_name = _probe_model_name(use_tiny=True)
            client = await llm._get_or_create_client("local", model_name, structured=False)

            start = time.perf_counter()

            text = await asyncio.wait_for(
                client.generate_text(prompt=prompt, max_tokens=1, temperature=0.0),
                timeout=budget_ms / 1000,
            )

            latency = (time.perf_counter() - start) * 1000
            return True, latency, str(text or "")
        except Exception as e:
            logger.debug(f"Transformers probe failed: {e}")
            return False, 0, None

    # =============================================================================
    # ENDPOINTS
    # =============================================================================

    @router.post(
        "/probe",
        response_model=ProbeResponse,
        responses=get_error_responses(400, 401, 403, 429, 500, 503),
        dependencies=[Depends(require_permission(Permission.SYSTEM_READ))],  # type: ignore[func-returns-value]
    )
    @enforce_tier1("rate_limit")
    async def inference_probe(request: ProbeRequest) -> ProbeResponse:
        """Probe local inference backend availability and latency.

        Tests the smallest available model with a tiny prompt to measure
        inference latency. Useful for health checks and budget estimation.
        """
        prompt = request.prompt
        budget_ms = request.budget_ms
        backend = request.backend or "auto"

        # Try backends in order
        backends_to_try = ["transformers", "api"] if backend == "auto" else [backend]

        for be in backends_to_try:
            if be == "transformers":
                success, latency, output = await _probe_transformers(prompt, budget_ms)
                if success:
                    if _LOCAL_INF_MS:
                        try:
                            _LOCAL_INF_MS.labels(backend="transformers").set(latency)
                        except Exception:
                            pass

                    status = "ok" if latency < budget_ms else "slow"
                    return ProbeResponse(
                        status=status,
                        latency_ms=round(latency, 2),
                        backend="transformers",
                        model=_probe_model_name(use_tiny=request.use_tiny),
                        output=output,
                    )
            if be == "api":
                # Probe OpenAI-compatible endpoint (if configured)
                import os

                base_url = os.getenv("KAGAMI_LLM_API_BASE_URL")
                if not base_url:
                    continue
                try:
                    import asyncio

                    from kagami.core.services.llm import get_llm_service

                    llm = get_llm_service()
                    model_name = os.getenv("KAGAMI_LLM_API_MODEL", "deepseek-ai/DeepSeek-V3.2-Exp")
                    client = await llm._get_or_create_client(
                        "api", model_name, structured=False, base_url=base_url
                    )
                    start = time.perf_counter()
                    text = await asyncio.wait_for(
                        client.generate_text(prompt=prompt, max_tokens=1, temperature=0.0),
                        timeout=budget_ms / 1000,
                    )
                    latency = (time.perf_counter() - start) * 1000
                    status = "ok" if latency < budget_ms else "slow"
                    return ProbeResponse(
                        status=status,
                        latency_ms=round(latency, 2),
                        backend="api",
                        model=model_name,
                        output=str(text or ""),
                    )
                except Exception as e:
                    logger.debug("API probe failed: %s", e)
                    continue

        # No backend available
        return ProbeResponse(
            status="failed",
            latency_ms=0,
            backend="none",
            model=None,
            output=None,
        )

    @router.post(
        "/generate",
        response_model=GenerateResponse,
        responses=get_error_responses(400, 401, 403, 429, 500, 503),
        dependencies=[Depends(require_permission(Permission.TOOL_EXECUTE))],  # type: ignore[func-returns-value]
    )
    @enforce_tier1("process")
    async def generate_text(request: GenerateRequest) -> GenerateResponse:
        """Generate text using local inference.

        Uses HuggingFace Transformers (MPS/CUDA/CPU) or remote API.
        """
        start = time.perf_counter()

        # Canonical: use LLM service with explicit local transformers provider.
        try:
            from kagami.core.services.llm import get_llm_service

            llm = get_llm_service()
            model_name = request.model or _probe_model_name(use_tiny=False)
            client = await llm._get_or_create_client("local", model_name, structured=False)
            text = await client.generate_text(
                prompt=request.prompt,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
            )
            latency = (time.perf_counter() - start) * 1000
            # We don't have exact token accounting here; return requested budget as conservative proxy.
            return GenerateResponse(
                text=str(text or ""),
                tokens_generated=request.max_tokens,
                latency_ms=round(latency, 2),
                model=str(model_name),
                finish_reason="length",
            )
        except Exception as e:
            logger.error("Local transformers generation failed: %s", e)

        raise HTTPException(
            status_code=503,
            detail={
                "code": "K-5003",
                "message": "No local inference backend available",
                "guidance": [
                    "Configure a local HF model (KAGAMI_TRANSFORMERS_MODEL_DEFAULT)",
                    "Or configure an OpenAI-compatible endpoint (KAGAMI_LLM_API_BASE_URL) and use provider=api",
                ],
            },
        )

    @router.get(
        "/models",
        response_model=ModelsResponse,
        responses=get_error_responses(401, 403, 429, 500),
        dependencies=[Depends(require_permission(Permission.SYSTEM_READ))],  # type: ignore[func-returns-value]
    )
    @enforce_tier1("rate_limit")
    async def list_models() -> ModelsResponse:
        """List available local models."""
        models: list[ModelInfo] = []
        default_model = None

        # List cached HF models (best-effort).
        try:
            from kagami.core.services.llm.cached_model_resolver import get_cached_models

            cached = get_cached_models()
            for m in cached:
                models.append(
                    ModelInfo(
                        name=m.name,
                        backend="transformers",
                        size_gb=float(m.size_gb or 0.0),
                        loaded=False,
                        capabilities=list(m.capabilities or []),
                    )
                )
            default_model = (
                default_model or _probe_model_name(use_tiny=False) or "Qwen/Qwen2.5-14B-Instruct"
            )
        except Exception:
            default_model = default_model or _probe_model_name(use_tiny=False)

        return ModelsResponse(models=models, default_model=default_model)

    @router.get(
        "/health",
        responses=get_error_responses(401, 403, 429, 500),
        dependencies=[Depends(require_permission(Permission.SYSTEM_READ))],  # type: ignore[func-returns-value]
    )
    @enforce_tier1("rate_limit")
    async def inference_health() -> dict[str, Any]:
        """Check local inference health status."""
        # We consider transformers available if we can import the LLM service.
        transformers_available = True
        try:
            from kagami.core.services.llm import get_llm_service  # noqa: F401
        except Exception:
            transformers_available = False
        import os

        api_available = bool(os.getenv("KAGAMI_LLM_API_BASE_URL"))

        overall = "healthy" if transformers_available or api_available else "unhealthy"

        return {
            "status": overall,
            "backends": {
                "transformers": {
                    "status": "available" if transformers_available else "unavailable"
                },
                "api": {"status": "available" if api_available else "unavailable"},
            },
        }

    return router
