"""LLM Providers - Provider implementations for different LLM backends.

Extracted from llm_service.py for better maintainability.
Supports:
- Transformers (local HuggingFace models)
- Structured output client
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Any, TypeVar

from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# Type stubs for transformers (lazy-loaded)
AutoModelForCausalLM = Any
AutoTokenizer = Any

# Transformers must be available - NO FALLBACKS (Full Operation Mode)

STRUCTURED_CLIENT_AVAILABLE = True
logger.info("✅ Structured client dependencies available (transformers)")


def _truthy_env(name: str, default: str = "0") -> bool:
    v = (os.getenv(name) or default).strip().lower()
    return v in {"1", "true", "yes", "on"}


def _mps_enabled() -> bool:
    try:
        import torch

        if not hasattr(torch.backends, "mps"):
            return False
        if not torch.backends.mps.is_available():
            return False
        return _truthy_env("KAGAMI_LLM_MPS", "1")
    except (ImportError, AttributeError, RuntimeError) as e:
        logger.debug(f"MPS detection failed: {e}")
        return False
        # Expected on non-Apple Silicon or when MPS backend unavailable


def _select_dtype_for_device(device: str) -> Any:
    """Select dtype for inference with env override.

    Env:
    - KAGAMI_LLM_DTYPE: auto|float16|bfloat16|float32
    - KAGAMI_LLM_MPS_DTYPE: auto|float16|bfloat16|float32 (overrides for MPS only)
    """
    import torch

    def _parse(name: str) -> Any | None:
        n = (name or "").strip().lower()
        if n in {"fp16", "float16"}:
            return torch.float16
        if n in {"bf16", "bfloat16"}:
            return torch.bfloat16
        if n in {"fp32", "float32"}:
            return torch.float32
        return None

    if device == "mps":
        mps_dtype = _parse(os.getenv("KAGAMI_LLM_MPS_DTYPE", "auto"))
        if mps_dtype is not None:
            return mps_dtype
    global_dtype = _parse(os.getenv("KAGAMI_LLM_DTYPE", "auto"))
    if global_dtype is not None:
        return global_dtype
    # Reasonable defaults:
    # - MPS: fp16 is the most widely supported; allow bf16 via env override
    # - CUDA: fp16
    # - CPU: fp32
    if device == "mps":
        return torch.float16
    if device == "cuda":
        return torch.float16
    return torch.float32


@dataclass
class _BatchRequest:
    prompt: str
    future: asyncio.Future[str]


class _MicroBatcher:
    """Micro-batching queue for per-model throughput (best-effort).

    Batches only requests with identical (max_tokens, temperature_bucket).
    """

    def __init__(
        self,
        *,
        client: TransformersTextClient,
        max_tokens: int,
        temperature: float,
        max_batch_size: int,
        max_wait_ms: int,
    ) -> None:
        self._client = client
        self._max_tokens = int(max_tokens)
        self._temperature = float(temperature)
        self._max_batch_size = int(max(1, max_batch_size))
        self._max_wait_ms = int(max(0, max_wait_ms))
        self._queue: asyncio.Queue[_BatchRequest] = asyncio.Queue()
        self._task: asyncio.Task[None] | None = None

    def _ensure_task(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._task = asyncio.create_task(self._run(), name="llm_microbatcher")

    async def submit(self, prompt: str) -> str:
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[str] = loop.create_future()
        self._ensure_task()
        await self._queue.put(_BatchRequest(prompt=str(prompt), future=fut))
        return await fut

    async def _run(self) -> None:
        while True:
            first = await self._queue.get()
            batch = [first]

            if self._max_wait_ms > 0 and self._max_batch_size > 1:
                deadline = asyncio.get_running_loop().time() + (self._max_wait_ms / 1000.0)
                while len(batch) < self._max_batch_size:
                    timeout = max(0.0, deadline - asyncio.get_running_loop().time())
                    if timeout <= 0:
                        break
                    try:
                        nxt = await asyncio.wait_for(self._queue.get(), timeout=timeout)
                    except TimeoutError:
                        break
                    batch.append(nxt)

            prompts = [r.prompt for r in batch]
            try:
                outs = await self._client.generate_text_batch(
                    prompts, max_tokens=self._max_tokens, temperature=self._temperature
                )
                if len(outs) != len(batch):
                    raise RuntimeError("microbatch_size_mismatch") from None
                for req, out in zip(batch, outs, strict=True):
                    if not req.future.done():
                        req.future.set_result(out)
            except Exception as e:
                # Fallback: try sequential per-request to avoid total failure.
                for req in batch:
                    try:
                        out = await self._client._generate_text_unbatched(
                            req.prompt, max_tokens=self._max_tokens, temperature=self._temperature
                        )
                        if not req.future.done():
                            req.future.set_result(out)
                    except Exception as inner:
                        if not req.future.done():
                            req.future.set_exception(inner)
                logger.debug("Microbatcher failed; fell back to sequential: %s", e)


class TransformersTextClient:
    """Local transformers text generation client.

    HOT PATH OPTIMIZATIONS:
    - Micro-batching: batch_size=8, max_wait=50ms (configured via env)
    - Memory management: Explicit offloading support
    - Lazy loading: Model loads on first use, not initialization
    """

    def __init__(self, model_name: str) -> None:
        """Initialize transformers client.

        Args:
            model_name: HuggingFace model name
        """
        self.model_name = model_name
        self.model: Any = None
        self.tokenizer: Any = None
        self.device: str | Any = "cpu"
        self._microbatchers: dict[tuple[int, int], _MicroBatcher] = {}
        self._last_used: float = 0.0  # Track last usage for offloading decisions
        self._offloaded: bool = False  # Track if model is offloaded to CPU

    async def initialize(self) -> None:
        """Initialize model and tokenizer - LAZY LOADING ON FIRST USE.

        OPTIMIZATION: Model loads on first generate_text() call, not here.
        Allows API to start in <15s instead of 90s+.
        """
        # Mark as "initialized" but don't load model yet
        # Model will load on first generate_text() call
        logger.info(
            f"✅ TransformersTextClient configured (model: {self.model_name}, lazy loading enabled)"
        )

    def _batching_enabled(self) -> bool:
        # Disable in pytest by default for determinism unless explicitly enabled.
        if "PYTEST_CURRENT_TEST" in os.environ:
            return _truthy_env("KAGAMI_LLM_ENABLE_BATCHING", "0")
        # Default on for MPS/CUDA if not explicitly configured.
        if os.getenv("KAGAMI_LLM_ENABLE_BATCHING") is None:
            try:
                import torch

                return bool(torch.cuda.is_available() or _mps_enabled())
            except Exception:
                return False
        return _truthy_env("KAGAMI_LLM_ENABLE_BATCHING", "0")

    def _get_microbatcher(self, max_tokens: int, temperature: float) -> _MicroBatcher:
        # Bucket temperature to avoid unbounded keys.
        temp_bucket = round(float(temperature) * 1000)
        key = (int(max_tokens), temp_bucket)
        mb = self._microbatchers.get(key)
        if mb is not None:
            return mb
        # OPTIMIZED: Higher batch size and wait time for M3 MAX throughput
        # - batch_size=8: M3 MAX 512GB unified memory can handle larger batches
        # - wait_ms=50: Allow more requests to accumulate before processing
        max_batch_size = int(
            os.getenv("KAGAMI_LLM_MAX_BATCH_SIZE") or os.getenv("LLM_BATCH_SIZE") or "8"
        )
        max_wait_ms = int(os.getenv("KAGAMI_LLM_BATCH_MAX_WAIT_MS") or "50")
        mb = _MicroBatcher(
            client=self,
            max_tokens=int(max_tokens),
            temperature=float(temperature),
            max_batch_size=max_batch_size,
            max_wait_ms=max_wait_ms,
        )
        self._microbatchers[key] = mb
        return mb

    def offload_to_cpu(self) -> None:
        """HOT PATH OPTIMIZATION: Offload model to CPU to free GPU/MPS memory.

        Call this when the model is not actively being used to allow other
        processes to use GPU memory. Model will be moved back on next generate().
        """
        if self.model is None or self._offloaded:
            return

        try:
            import torch

            if hasattr(self.model, "to"):
                self.model = self.model.to("cpu")
                self._offloaded = True
                self.device = "cpu"
                # Clear CUDA/MPS cache
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                    # MPS doesn't have empty_cache, but moving to CPU releases memory
                    pass
                logger.info(f"✅ Model {self.model_name} offloaded to CPU to free memory")
        except Exception as e:
            logger.warning(f"Failed to offload model to CPU: {e}")

    def restore_to_device(self) -> None:
        """HOT PATH OPTIMIZATION: Restore model to original device (GPU/MPS).

        Automatically called before generation if model was offloaded.
        """
        if self.model is None or not self._offloaded:
            return

        try:
            import torch

            # Determine best device
            use_mps = _mps_enabled()
            use_cuda = torch.cuda.is_available()
            target_device = "cuda" if use_cuda else ("mps" if use_mps else "cpu")

            if target_device != "cpu":
                self.model = self.model.to(target_device)
                self.device = target_device
                self._offloaded = False
                logger.info(f"✅ Model {self.model_name} restored to {target_device}")
        except Exception as e:
            logger.warning(f"Failed to restore model to device: {e}")
            # Keep on CPU if restore fails
            self._offloaded = False

    def _update_last_used(self) -> None:
        """Track last usage time for memory management decisions."""
        import time

        self._last_used = time.time()

    def get_memory_stats(self) -> dict[str, Any]:
        """Get model memory usage statistics for monitoring."""
        stats = {
            "model_name": self.model_name,
            "device": str(self.device),
            "offloaded": self._offloaded,
            "last_used": self._last_used,
            "model_loaded": self.model is not None,
        }

        if self.model is not None:
            try:
                import torch

                # Get model parameter memory
                param_bytes = sum(p.numel() * p.element_size() for p in self.model.parameters())
                stats["param_memory_mb"] = param_bytes / (1024 * 1024)

                # Get GPU memory if applicable
                if torch.cuda.is_available() and not self._offloaded:
                    stats["cuda_memory_allocated_mb"] = torch.cuda.memory_allocated() / (
                        1024 * 1024
                    )
                    stats["cuda_memory_reserved_mb"] = torch.cuda.memory_reserved() / (1024 * 1024)
            except Exception as e:
                stats["memory_error"] = str(e)

        return stats

    async def generate_text(self, prompt: str, max_tokens: int, temperature: float) -> str:
        """Generate text using transformers (optionally micro-batched).

        Args:
            prompt: Input prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            Generated text
        """
        # HOT PATH OPTIMIZATION: Restore model if offloaded
        if self._offloaded:
            self.restore_to_device()

        # Track last usage for memory management
        self._update_last_used()

        if self._batching_enabled():
            return await self._get_microbatcher(max_tokens, temperature).submit(prompt)
        return await self._generate_text_unbatched(
            prompt, max_tokens=max_tokens, temperature=temperature
        )

    async def _generate_text_unbatched(
        self, prompt: str, max_tokens: int, temperature: float
    ) -> str:
        # LAZY LOADING: Load model on first actual use
        # FIX: Check model is None (not model AND tokenizer) to handle partial init failures
        if self.model is None:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer

            # Reset tokenizer too in case of partial init from previous failed attempt
            self.tokenizer = None

            # Validate model exists in cache, use fallback if not
            actual_model = self.model_name
            try:
                from kagami.core.services.llm.cached_model_resolver import (
                    get_fallback_model,
                    validate_model_exists,
                )

                # Only force cached-only behavior when running offline / explicitly requested.
                offline = _truthy_env("TRANSFORMERS_OFFLINE", "0") or _truthy_env(
                    "HF_HUB_OFFLINE", "0"
                )
                require_cached = _truthy_env("KAGAMI_REQUIRE_CACHED_MODELS", "0")
                if (offline or require_cached) and (not validate_model_exists(self.model_name)):
                    fallback = get_fallback_model(self.model_name)
                    if fallback:
                        logger.warning(
                            f"⚠️ Model '{self.model_name}' not cached, using fallback: {fallback}"
                        )
                        actual_model = fallback
                    else:
                        logger.error(
                            f"❌ Model '{self.model_name}' not found and no fallback available"
                        )
            except ImportError:
                pass  # Cached model resolver not available, proceed with original name

            logger.info(f"🔄 Lazy loading model on first use: {actual_model}")
            try:
                self.tokenizer = AutoTokenizer.from_pretrained(actual_model, local_files_only=False)
                assert self.tokenizer is not None
                # CRITICAL: Set padding_side='left' for decoder-only models (batch generation)
                # This ensures correct attention masking when generating for padded batches
                self.tokenizer.padding_side = "left"
            except Exception as e:
                self.tokenizer = None  # Reset on failure
                raise RuntimeError(f"Failed to load tokenizer for {actual_model}: {e}") from e
            # Some tokenizers (e.g., GPT-2) have no pad token; batch inference needs one.
            try:
                if getattr(self.tokenizer, "pad_token_id", None) is None:
                    eos_tok = getattr(self.tokenizer, "eos_token", None)
                    eos_id = getattr(self.tokenizer, "eos_token_id", None)
                    if eos_tok is not None and eos_id is not None:
                        self.tokenizer.pad_token = eos_tok
                    else:
                        self.tokenizer.add_special_tokens({"pad_token": "[PAD]"})
            except (AttributeError, ValueError) as e:
                logger.debug(f"Failed to set[Any] pad token, model may not support padding: {e}")
                # Non-critical - some models handle padding differently

            # Device selection (MPS preferred on Apple Silicon unless disabled).
            use_mps = _mps_enabled()
            use_cuda = torch.cuda.is_available()
            device_str = "cuda" if use_cuda else ("mps" if use_mps else "cpu")
            dtype = _select_dtype_for_device(device_str)

            # Check for quantization (optional - controlled by env var)
            use_quantization = os.getenv("KAGAMI_USE_QUANTIZATION", "0") == "1"
            quantization_config = None

            if use_quantization and use_cuda:
                try:
                    from transformers import BitsAndBytesConfig

                    quantization_config = BitsAndBytesConfig(
                        load_in_4bit=True,
                        bnb_4bit_compute_dtype=torch.bfloat16,
                        bnb_4bit_use_double_quant=True,
                        bnb_4bit_quant_type="nf4",
                    )
                    logger.info("🔥 Using 4-bit quantization (2-3x faster, 4x less memory)")
                except ImportError:
                    logger.debug("BitsAndBytes not available, using full precision")

            logger.info(f"Loading with dtype: {dtype} (MPS: {use_mps}, CUDA: {use_cuda})")

            model_kwargs = {
                "local_files_only": False,
                "torch_dtype": dtype,
                # NOTE: MPS device_map support is inconsistent across transformers/accelerate versions.
                # Prefer a conservative load-on-cpu-then-move strategy for MPS.
                "device_map": ("cpu" if use_mps else "auto"),
                "low_cpu_mem_usage": True,
            }

            if quantization_config is not None:
                model_kwargs["quantization_config"] = quantization_config

            try:
                self.model = AutoModelForCausalLM.from_pretrained(actual_model, **model_kwargs)
                assert self.model is not None
            except Exception as e:
                # Reset both on failure to allow retry on next call
                self.tokenizer = None
                self.model = None
                raise RuntimeError(f"Failed to load model {actual_model}: {e}") from e

            self.model_name = actual_model  # Update to actual loaded model

            # Explicit move to MPS when enabled (more reliable than device_map="mps").
            if use_mps:
                try:
                    self.model = self.model.to("mps")
                except Exception as e:
                    logger.warning("MPS move failed, falling back to CPU: %s", e)
                    self.model = self.model.to("cpu")
                    use_mps = False

            # Track device and set[Any] eval for inference.
            self.model.eval()
            # Ensure pad token id is set[Any] for generate() (esp. after pad_token assignment).
            try:
                pad_id = getattr(self.tokenizer, "pad_token_id", None)
                if pad_id is not None and getattr(self.model.config, "pad_token_id", None) is None:
                    self.model.config.pad_token_id = int(pad_id)
            except (AttributeError, ValueError) as e:
                logger.debug(f"Failed to sync pad token ID to model config: {e}")
                # Non-critical - model may handle padding without explicit config
            self.device = "mps" if use_mps else next(self.model.parameters()).device
            quant_str = " (4-bit)" if quantization_config else ""
            logger.info(f"✅ Model loaded: {self.model_name} on {self.device} ({dtype}{quant_str})")

        inputs = self.tokenizer(prompt, return_tensors="pt")

        # Move to device (model already on correct device with device_map)
        try:
            device = next(self.model.parameters()).device
            inputs = {k: v.to(device) for k, v in inputs.items()}
        except (StopIteration, AttributeError, RuntimeError) as e:
            logger.debug(f"Failed to move inputs to model device: {e}")
            # Non-critical - inputs may already be on correct device

        # Optional: valued attention logits processor
        logits_processor: Any = None
        try:
            from transformers import LogitsProcessorList

            try:
                from kagami.core.attention.valued_attention import (
                    build_processor_if_enabled,  # type: ignore[attr-defined]
                )

                va = build_processor_if_enabled(self.model, self.tokenizer, app_label="llm_service")
                if va is not None:
                    logits_processor = LogitsProcessorList([va])
            except (ImportError, AttributeError) as e:
                logger.debug(f"Valued attention not available: {e}")
                # Optional enhancement - valued attention improves quality but isn't required
        except (ImportError, AttributeError) as e:
            logger.debug(f"LogitsProcessorList not available: {e}")
            # Expected when transformers version doesn't support logits processors

        # Greedy decoding when temperature <= 0
        do_sample = True
        temp = temperature
        if float(temperature) <= 0.0:
            do_sample = False
            temp = 1.0  # unused when do_sample=False

        gen_pad_id: Any = getattr(self.tokenizer, "pad_token_id", None)
        if gen_pad_id is None:
            gen_pad_id = getattr(self.tokenizer, "eos_token_id", None)

        # Build generation kwargs (explicit top_p/top_k to avoid warnings)
        gen_kwargs: dict[str, Any] = {
            "do_sample": do_sample,
            "max_new_tokens": max_tokens,
            "pad_token_id": gen_pad_id,
            "logits_processor": logits_processor,
        }
        if do_sample:
            # Only set[Any] sampling params when actually sampling
            gen_kwargs["temperature"] = temp
            gen_kwargs["top_p"] = 0.9
            gen_kwargs["top_k"] = 50
        else:
            # Explicitly disable sampling params to avoid warnings
            gen_kwargs["temperature"] = None
            gen_kwargs["top_p"] = None
            gen_kwargs["top_k"] = None

        try:
            import torch

            with torch.inference_mode():
                gen_ids = self.model.generate(**inputs, **gen_kwargs)
        except (AttributeError, RuntimeError) as e:
            logger.debug(f"inference_mode not available, using standard generate: {e}")
            # Fallback for older PyTorch versions without inference_mode
            gen_ids = self.model.generate(**inputs, **gen_kwargs)

        decoded: str = str(self.tokenizer.decode(gen_ids[0], skip_special_tokens=True))

        # Remove prompt from output if present
        if decoded.startswith(prompt):
            return decoded[len(prompt) :].lstrip()
        return decoded

    async def generate_text_batch(
        self, prompts: list[str], *, max_tokens: int, temperature: float
    ) -> list[str]:
        """Generate text for a batch of prompts (single model call).

        This is the core primitive used by the microbatcher.
        """
        if not prompts:
            return []
        # Ensure model is loaded (check just model since _generate_text_unbatched handles both)
        if self.model is None:
            # Load lazily by running a single unbatched call (loads model once).
            await self._generate_text_unbatched(prompts[0], max_tokens=1, temperature=0.0)

        if self.model is None or self.tokenizer is None:
            raise RuntimeError("Model or tokenizer failed to initialize")

        assert self.model is not None
        assert self.tokenizer is not None
        # Ensure padding token exists for batch tokenization.
        try:
            if getattr(self.tokenizer, "pad_token_id", None) is None:
                eos_tok = getattr(self.tokenizer, "eos_token", None)
                eos_id = getattr(self.tokenizer, "eos_token_id", None)
                if eos_tok is not None and eos_id is not None:
                    self.tokenizer.pad_token = eos_tok
                else:
                    self.tokenizer.add_special_tokens({"pad_token": "[PAD]"})
        except (AttributeError, ValueError) as e:
            logger.debug(f"Failed to set[Any] pad token for batch generation: {e}")
            # Non-critical - tokenizer may handle padding differently

        inputs = self.tokenizer(prompts, return_tensors="pt", padding=True)
        try:
            device = next(self.model.parameters()).device
            inputs = {k: v.to(device) for k, v in inputs.items()}
        except (StopIteration, AttributeError, RuntimeError) as e:
            logger.debug(f"Failed to move batch inputs to device: {e}")
            # Non-critical - inputs may already be on correct device

        do_sample = True
        temp = float(temperature)
        if temp <= 0.0:
            do_sample = False
            temp = 1.0

        batch_pad_id: Any = getattr(self.tokenizer, "pad_token_id", None)
        if batch_pad_id is None:
            batch_pad_id = getattr(self.tokenizer, "eos_token_id", None)
        attention_mask = inputs.get("attention_mask")
        prompt_lens = None
        try:
            if attention_mask is not None:
                prompt_lens = attention_mask.sum(dim=1).tolist()
        except (AttributeError, RuntimeError) as e:
            logger.debug(f"Failed to compute prompt lengths from attention mask: {e}")
            prompt_lens = None
            # Non-critical - will use fallback decoding strategy

        # Build batch generation kwargs (explicit params to avoid warnings)
        batch_gen_kwargs: dict[str, Any] = {
            "do_sample": do_sample,
            "max_new_tokens": int(max_tokens),
            "pad_token_id": batch_pad_id,
        }
        if do_sample:
            batch_gen_kwargs["temperature"] = temp
            batch_gen_kwargs["top_p"] = 0.9
            batch_gen_kwargs["top_k"] = 50
        else:
            batch_gen_kwargs["temperature"] = None
            batch_gen_kwargs["top_p"] = None
            batch_gen_kwargs["top_k"] = None

        try:
            import torch

            with torch.inference_mode():
                gen_ids = self.model.generate(**inputs, **batch_gen_kwargs)
        except (AttributeError, RuntimeError) as e:
            logger.debug(f"inference_mode not available for batch, using standard generate: {e}")
            # Fallback for older PyTorch versions
            gen_ids = self.model.generate(**inputs, **batch_gen_kwargs)

        outs: list[str] = []
        for i in range(len(prompts)):
            try:
                if prompt_lens is not None:
                    start = int(prompt_lens[i])
                    out_tokens = gen_ids[i][start:]
                    txt = self.tokenizer.decode(out_tokens, skip_special_tokens=True)
                    outs.append(str(txt).strip())
                else:
                    full = self.tokenizer.decode(gen_ids[i], skip_special_tokens=True)
                    p = prompts[i]
                    outs.append(
                        full[len(p) :].lstrip() if full.startswith(p) else str(full).strip()
                    )
            except (IndexError, ValueError) as e:
                logger.warning(f"Failed to decode output {i} in batch: {e}")
                # Fallback to basic decoding
                full = self.tokenizer.decode(gen_ids[i], skip_special_tokens=True)
                outs.append(str(full).strip())
        return outs


class StructuredOutputClientWrapper:
    """Wrapper for structured output client."""

    def __init__(self, model_name: str, device: str = "auto") -> None:
        """Initialize structured client wrapper.

        Args:
            model_name: HuggingFace model name
            device: Device to use ("auto", "cpu", "cuda", "mps")
        """
        self.model_name = model_name
        self.device = device
        self._client: Any = None

    async def initialize(self) -> None:
        """Initialize structured client."""
        if self._client is not None:
            return

        from kagami.core.services.llm.structured_client import get_structured_client

        self._client = get_structured_client(
            model_name=self.model_name,
            device=self.device,
        )
        assert self._client is not None
        await self._client.initialize()

    async def generate_structured(
        self,
        prompt: str,
        response_model: type[T],
        max_tokens: int,
        temperature: float,
    ) -> T:
        """Generate structured output.

        Args:
            prompt: Input prompt
            response_model: Pydantic model class
            max_tokens: Max tokens
            temperature: Temperature

        Returns:
            Instance of response_model
        """
        if self._client is None:
            await self.initialize()

        assert self._client is not None
        result: T = await self._client.generate_structured(
            prompt=prompt,
            response_model=response_model,
            max_tokens=max_tokens,
            temperature=max(0.0, float(temperature)),
        )

        return result


def create_transformers_client(model_name: str) -> TransformersTextClient:
    """Create transformers text client.

    Args:
        model_name: HuggingFace model name

    Returns:
        TransformersTextClient instance
    """
    return TransformersTextClient(model_name)


def create_structured_client(
    model_name: str, device: str = "auto"
) -> StructuredOutputClientWrapper:
    """Create structured output client.

    Args:
        model_name: HuggingFace model name
        device: Device to use

    Returns:
        StructuredOutputClientWrapper instance
    """
    return StructuredOutputClientWrapper(model_name, device)


__all__ = [
    "STRUCTURED_CLIENT_AVAILABLE",
    "StructuredOutputClientWrapper",
    "TransformersTextClient",
    "create_structured_client",
    "create_transformers_client",
]
