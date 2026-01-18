from __future__ import annotations

"""Structured Output Client using Instructor + Transformers + LoRA.

This module provides structured output generation using:
1. Instructor library - Industry best practice for Pydantic-constrained outputs
2. Transformers + PEFT - For loading finetuned LoRA adapters
3. Local model weights - Uses actual finetuned weights, not API calls

Based on research (2025):
- Instructor by Jason Liu is the most popular structured output library
- PEFT for efficient adapter loading
- Outlines as fallback for constrained generation
"""
import importlib
import logging
import os
from pathlib import Path
from typing import Any, TypeVar

import torch
from pydantic import BaseModel

# Import transformers - NO FALLBACKS (Full Operation Mode)
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    PreTrainedModel,
    PreTrainedTokenizer,
)

TRANSFORMERS_AVAILABLE = True

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# Try instructor first (best practice)
try:
    import instructor  # noqa: F401 - availability check
    from instructor import Instructor  # noqa: F401

    INSTRUCTOR_AVAILABLE = True
    logger.info("✅ Instructor library available")
except ImportError:
    INSTRUCTOR_AVAILABLE = False
    logger.warning("Instructor not available. Install: pip install instructor")

# PEFT for LoRA adapter loading
try:
    from peft import PeftModel

    PEFT_AVAILABLE = True
except ImportError:
    PEFT_AVAILABLE = False
    logger.warning("PEFT not available. Install: pip install peft")


class StructuredOutputClient:
    """Client for generating structured outputs with finetuned model weights.

    Features:
    - Loads actual model weights (not API calls)
    - Supports LoRA adapters for finetuning
    - Uses instructor for Pydantic-constrained outputs
    - Falls back to outlines if instructor unavailable
    """

    def __init__(
        self,
        model_name: str = "Qwen/Qwen2.5-14B-Instruct",  # Compatible default (non-MoE)
        adapter_path: str | None = None,
        device: str = "auto",
        load_in_4bit: bool = False,  # Disabled for 512GB
        load_in_8bit: bool = False,  # Disabled for 512GB
    ) -> None:
        """Initialize structured output client with model weights.

        M3 MAX 512GB OPTIMIZATION: Full precision, MPS acceleration, massive parallelism

        NOTE: Qwen3-Coder-30B-A3B (MoE) requires transformers >=4.50
        Default to Qwen2.5-14B-Instruct for compatibility.
        Upgrade transformers to use MoE: pip install transformers --upgrade

        Args:
            model_name: Base model to load (default: Qwen2.5-14B-Instruct, compatible)
            adapter_path: Optional LoRA adapter path (e.g. models/kagami-lora)
            device: Device to use (auto, cuda, mps, cpu) - M3 MAX defaults to MPS
            load_in_4bit: Use 4-bit quantization (DISABLED for 512GB - use full precision)
            load_in_8bit: Use 8-bit quantization (DISABLED for 512GB)
        """
        self.model_name = model_name
        self.adapter_path = adapter_path
        self.device = self._resolve_device(device)
        self.load_in_4bit = load_in_4bit
        self.load_in_8bit = load_in_8bit

        self.model: PreTrainedModel | None = None
        self.tokenizer: PreTrainedTokenizer | None = None
        self.instructor_client: Any | None = None

        self._initialized = False

        # Optional: LLM+WM+CBF pipeline for safe generation
        self._pipeline = None
        self._use_safe_pipeline = os.getenv("KAGAMI_USE_SAFE_PIPELINE", "0") == "1"

    def _get_fallback_model(self) -> str | None:
        """Get a fallback model from cache when primary model isn't supported.

        Returns:
            Fallback model name, or None if no suitable fallback found.
        """
        # Priority: coder > flagship > instruct (from cached models)
        try:
            from kagami.core.services.llm.cached_model_resolver import (
                find_best_model,
                get_cached_models,
            )

            # Try coder models first (non-MoE variants)
            for model in get_cached_models():
                # Skip MoE models (need newer transformers)
                if "A3B" in model.name or "moe" in model.name.lower():
                    continue
                # Prefer Qwen instruct models
                if "coder" in model.capabilities and "instruct" in model.capabilities:
                    logger.info(f"Found fallback coder model: {model.name}")
                    return model.name

            # Fallback to any instruct model with good size
            for model in get_cached_models():
                if "A3B" in model.name or "moe" in model.name.lower():
                    continue
                if "instruct" in model.capabilities and model.size_gb >= 10:
                    logger.info(f"Found fallback instruct model: {model.name}")
                    return model.name

            # Last resort: any instruct model
            fallback = find_best_model("instruct")
            if fallback:
                return fallback.name

        except Exception as e:
            logger.debug(f"Fallback model lookup failed: {e}")

        # Hardcoded fallback for known working models
        return "Qwen/Qwen2.5-14B-Instruct"

    def _resolve_device(self, device: str) -> str:
        """Resolve device string to actual device.

        M3 MAX 512GB: MPS ENABLED BY DEFAULT (we have massive unified memory!)
        """
        if device == "auto":
            try:
                # M3 MAX: Default to MPS ON (override with KAGAMI_LLM_MPS=0 to disable)
                use_mps = os.getenv("KAGAMI_LLM_MPS", "1").lower() in (
                    "1",
                    "true",
                    "yes",
                    "on",
                )
            except Exception:
                use_mps = True  # Default to True for M3 MAX

            if torch.cuda.is_available():
                return "cuda"
            elif use_mps and hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                logger.info("✅ Using MPS (Metal Performance Shaders) for M3 MAX 512GB")
                return "mps"
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                # MPS available but disabled via env
                logger.info("MPS available but disabled (enable with KAGAMI_LLM_MPS=1)")
                return "cpu"
            else:
                return "cpu"
        return device

    async def initialize(self) -> None:
        """Load model weights and LoRA adapters."""
        if self._initialized:
            return

        if not TRANSFORMERS_AVAILABLE:
            logger.error("Cannot initialize: transformers library not available")
            raise RuntimeError("Transformers library required but not available")

        logger.info(f"Loading model: {self.model_name}")
        logger.info(f"Device: {self.device}")

        # Load tokenizer with fallback for unsupported architectures
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_name,
                trust_remote_code=True,
            )
            # CRITICAL: Set padding_side='left' for decoder-only models (batch generation)
            self.tokenizer.padding_side = "left"
        except (ValueError, KeyError) as e:
            # Model architecture not supported (e.g., qwen3_moe needs newer transformers)
            if "does not recognize this architecture" in str(e) or "qwen3_moe" in str(e):
                logger.warning(
                    f"Model {self.model_name} requires newer transformers. "
                    "Falling back to cached compatible model."
                )
                fallback = self._get_fallback_model()
                if fallback and fallback != self.model_name:
                    logger.info(f"Using fallback model: {fallback}")
                    self.model_name = fallback
                    self.tokenizer = AutoTokenizer.from_pretrained(
                        self.model_name,
                        trust_remote_code=True,
                    )
                    self.tokenizer.padding_side = "left"  # Decoder-only batch fix
                else:
                    raise RuntimeError(
                        f"Model {self.model_name} not supported and no fallback available. "
                        "Upgrade transformers: pip install transformers --upgrade"
                    ) from e
            else:
                logger.error(f"Failed to load tokenizer: {e}")
                raise RuntimeError(f"Tokenizer loading failed: {e}") from e
        except Exception as e:
            logger.error(f"Failed to load tokenizer: {e}")
            raise RuntimeError(f"Tokenizer loading failed: {e}") from e

        # Load base model - M3 MAX 512GB: FULL PRECISION, MPS optimized
        model_kwargs = {
            "trust_remote_code": True,
            # M3 MAX 512GB: Use bfloat16 for best MPS performance (no quantization needed!)
            "torch_dtype": torch.bfloat16 if self.device == "mps" else torch.float16,
        }

        # Quantization (DISABLED for M3 MAX 512GB - use full precision!)
        if self.load_in_4bit and self.device != "mps":
            # Only allow quantization on non-MPS devices if explicitly requested
            try:
                from transformers import BitsAndBytesConfig

                model_kwargs["quantization_config"] = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.float16,
                    bnb_4bit_use_double_quant=True,
                    bnb_4bit_quant_type="nf4",
                )
                logger.info("Using 4-bit quantization")
            except ImportError:
                logger.warning("bitsandbytes not available - skipping 4-bit")
        elif self.load_in_8bit and self.device != "mps":
            model_kwargs["load_in_8bit"] = True
            logger.info("Using 8-bit quantization")
        else:
            logger.info(f"✅ M3 MAX 512GB: Using FULL PRECISION {model_kwargs['torch_dtype']}")

        # Set device placement strategy
        # M3 MAX 512GB: Optimize for unified memory
        if not (self.load_in_4bit or self.load_in_8bit):
            if self.device in ("cuda", "cpu", "auto"):
                model_kwargs["device_map"] = self.device
            elif self.device == "mps":
                # MPS: Load on CPU first, then move (HF doesn't support device_map="mps")
                model_kwargs["device_map"] = "cpu"

        # M3 MAX 512GB: Enable flash attention for faster inference (CUDA-only)
        try:
            use_flash = os.getenv("KAGAMI_USE_FLASH_ATTENTION", "1").lower() in (
                "1",
                "true",
                "yes",
                "on",
            )
            if use_flash:
                device_is_cuda = (self.device in ("cuda", "auto")) and torch.cuda.is_available()
                if not device_is_cuda:
                    logger.debug(
                        "FlashAttention disabled: supported only on CUDA GPUs (device=%s)",
                        self.device,
                    )
                else:
                    try:
                        import flash_attn  # noqa: F401

                        model_kwargs["attn_implementation"] = "flash_attention_2"
                        logger.info("✅ Flash Attention 2 enabled (CUDA)")
                    except ImportError:
                        logger.info(
                            "FlashAttention2 package not installed; using standard attention."
                        )
        except Exception as e:
            logger.debug(f"FlashAttention configuration skipped: {e}")

        # Load model with architecture fallback
        logger.info(f"Loading {self.model_name} with {model_kwargs['torch_dtype']}")
        try:
            self.model = AutoModelForCausalLM.from_pretrained(self.model_name, **model_kwargs)
        except (ValueError, KeyError) as e:
            # Model architecture not supported - try fallback
            if "does not recognize this architecture" in str(e):
                fallback = self._get_fallback_model()
                if fallback and fallback != self.model_name:
                    logger.warning(f"Model architecture not supported. Falling back to {fallback}")
                    self.model_name = fallback
                    # Reload tokenizer for new model
                    self.tokenizer = AutoTokenizer.from_pretrained(
                        self.model_name, trust_remote_code=True
                    )
                    self.tokenizer.padding_side = "left"  # Decoder-only batch fix
                    self.model = AutoModelForCausalLM.from_pretrained(
                        self.model_name, **model_kwargs
                    )
                else:
                    raise
            else:
                raise

        # Explicit MPS move for M3 MAX unified memory
        if self.device == "mps":
            try:
                logger.info("Moving model to MPS (Metal Performance Shaders)...")
                self.model = self.model.to("mps")  # type: ignore[arg-type]
                logger.info("✅ Model on MPS device (M3 MAX 512GB optimized)")
            except Exception as e:
                logger.warning(f"MPS move failed, using CPU: {e}")
                try:
                    self.model = self.model.to("cpu")  # type: ignore[arg-type]
                    self.device = "cpu"
                except Exception:
                    pass

        # Load LoRA adapter if specified
        if self.adapter_path and PEFT_AVAILABLE:
            adapter_path = Path(self.adapter_path)
            if adapter_path.exists():
                # Check adapter config to verify model compatibility
                adapter_config_path = adapter_path / "adapter_config.json"
                if adapter_config_path.exists():
                    import json

                    with open(adapter_config_path) as f:
                        adapter_config = json.load(f)
                        adapter_base = adapter_config.get("base_model_name_or_path", "")

                        # Verify base model matches
                        if adapter_base and adapter_base != self.model_name:
                            logger.warning(
                                f"LoRA adapter base model mismatch: "
                                f"adapter trained on {adapter_base}, "
                                f"but loading on {self.model_name}. "
                                f"Skipping adapter loading."
                            )
                        else:
                            logger.info(f"Loading LoRA adapter from: {adapter_path}")
                            try:
                                self.model = PeftModel.from_pretrained(  # type: ignore[assignment]
                                    self.model, str(adapter_path)
                                )
                                logger.info("✅ LoRA adapter loaded successfully")
                            except Exception as e:
                                logger.warning(f"Failed to load LoRA adapter: {e}")
                else:
                    logger.warning(f"LoRA adapter config not found: {adapter_config_path}")
            else:
                logger.warning(f"LoRA adapter not found: {adapter_path}")

        # NOTE: For now, skip instructor integration - use direct model generation
        # This avoids litellm/Ollama API layer and uses actual loaded weights
        logger.info("Using direct model generation with loaded weights (no instructor)")

        self._initialized = True
        logger.info("✅ Structured output client initialized")

    async def generate_structured(
        self,
        prompt: str,
        response_model: type[T],
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> T:
        """Generate structured output conforming to Pydantic schema using loaded weights.

        Uses constrained generation to guarantee valid Pydantic output.

        Args:
            prompt: Input prompt
            response_model: Pydantic model class defining output schema
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            Instance of response_model with validated structured data
        """
        if not self._initialized:
            await self.initialize()

        # Use outlines for constrained generation with actual model weights
        try:
            import outlines
            import outlines.generate

            logger.info("Using outlines with loaded model weights")

            # Outlines 1.2+ API: Model wrapper
            model_wrapper = outlines.models.Transformers(model=self.model, tokenizer=self.tokenizer)  # type: ignore[arg-type]

            # Create JSON schema generator using modern API
            schema_dict = response_model.model_json_schema()
            generator = outlines.generate.json(model_wrapper, schema_dict)

            # Generate with constraints (sync call)
            result_text = generator(prompt)

            # Parse to Pydantic model
            import json

            result_data = json.loads(result_text) if isinstance(result_text, str) else result_text
            result = response_model(**result_data)

            logger.info("✅ Generated structured output via outlines")
            return result
        except Exception as e:
            # NO FALLBACK - enforce structured outputs
            logger.error(f"Outlines generation failed: {e}")
            raise RuntimeError(
                f"Structured output generation failed: {e}\n"
                "Outlines is required for constrained generation. No fallbacks."
            ) from e

    async def generate_text(
        self, prompt: str, max_tokens: int = 512, temperature: float = 0.7
    ) -> str:
        """Generate unstructured text output.

        Args:
            prompt: Input prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            Generated text string
        """
        if not self._initialized:
            await self.initialize()

        inputs = self.tokenizer(prompt, return_tensors="pt")  # type: ignore  # Misc
        if self.device != "cpu":
            inputs = {k: v.to(self.device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self.model.generate(  # type: ignore  # Union member
                **inputs,
                max_new_tokens=max_tokens,
                temperature=temperature,
                do_sample=temperature > 0,
                pad_token_id=self.tokenizer.eos_token_id,  # type: ignore  # Union member
            )

        generated_text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)  # type: ignore  # Union member

        # Remove prompt from output
        if generated_text.startswith(prompt):
            generated_text = generated_text[len(prompt) :].strip()

        return generated_text

    async def generate_safe(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
        app_name: str = "structured_client",
        max_tokens: int = 512,
        temperature: float = 0.7,
        n_candidates: int = 5,
    ) -> str:
        """Generate text with LLM+WM+CBF safety pipeline.

        This method uses the unified pipeline for safe, high-quality generation:
        1. Generate multiple candidates
        2. Predict outcomes with world model
        3. Filter with CBF
        4. Select best safe response

        Enable with: KAGAMI_USE_SAFE_PIPELINE=1

        Args:
            prompt: Input prompt
            context: Additional context for safety assessment
            app_name: Application name for logging
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            n_candidates: Number of candidates to generate

        Returns:
            Safe generated text
        """
        if self._use_safe_pipeline:
            # Use unified pipeline
            if self._pipeline is None:
                try:
                    pipeline_module = importlib.import_module(
                        "kagami.core.integration.llm_wm_cbf_pipeline"
                    )
                    get_pipeline = pipeline_module.get_pipeline
                    PipelineConfig = pipeline_module.PipelineConfig

                    self._pipeline = get_pipeline(
                        config=PipelineConfig(
                            n_candidates=n_candidates,
                            use_world_model=True,
                            use_cbf_filter=True,
                            batch_predictions=True,
                            enable_learning=True,
                        )
                    )
                    logger.info("✅ Safe pipeline enabled for structured client")
                except Exception as e:
                    logger.warning(f"Could not initialize safe pipeline: {e}, falling back")
                    self._use_safe_pipeline = False

            if self._pipeline is not None:
                try:  # type: ignore[unreachable]
                    result = await self._pipeline.process(
                        prompt=prompt,
                        context=context or {},
                        app_name=app_name,
                    )

                    if result.safe:
                        logger.info(
                            f"Safe generation: {result.candidates_safe}/{result.candidates_generated} "
                            f"candidates passed CBF (h_x={result.h_x:.3f})"
                        )
                        return result.response
                    else:
                        logger.warning(
                            f"No safe candidates found (h_x={result.h_x:.3f}), using fallback"
                        )
                        # Fall through to direct generation
                except Exception as e:
                    logger.warning(f"Safe pipeline failed: {e}, using direct generation")

        # Fallback: direct generation without pipeline
        return await self.generate_text(prompt, max_tokens, temperature)


# Global instance
_structured_client: StructuredOutputClient | None = None


def get_structured_client(
    model_name: str | None = None,
    adapter_path: str | None = None,
    device: str = "auto",
) -> StructuredOutputClient:
    """Get or create global structured output client.

    Args:
        model_name: Base model (default from env or Qwen2.5-1.5B for compatibility)
        adapter_path: LoRA adapter path (default: models/kagami-lora if exists AND matches)
        device: Device to use (auto, cuda, mps, cpu)

    Returns:
        StructuredOutputClient instance
    """
    global _structured_client

    # Resolve defaults
    if model_name is None:
        # M3 MAX 512GB: Default to FLAGSHIP 30B
        model_name = os.getenv("KAGAMI_BASE_MODEL", "Qwen/Qwen3-Coder-30B-A3B-Instruct")

    if adapter_path is None:
        # Auto-detect LoRA adapter and verify compatibility
        default_adapter = Path("models/kagami-lora")
        if default_adapter.exists():
            # Check if adapter matches model
            adapter_config_path = default_adapter / "adapter_config.json"
            if adapter_config_path.exists():
                import json

                with open(adapter_config_path) as f:
                    adapter_config = json.load(f)
                    adapter_base = adapter_config.get("base_model_name_or_path", "")

                    if adapter_base == model_name:
                        adapter_path = str(default_adapter)
                        logger.info(f"Auto-detected compatible LoRA adapter: {adapter_path}")
                    else:
                        logger.info(
                            f"Skipping LoRA adapter (base mismatch: {adapter_base} vs {model_name})"
                        )

    # Create new client if none exists or config changed
    if _structured_client is None:
        _structured_client = StructuredOutputClient(
            model_name=model_name,
            adapter_path=adapter_path,
            device=device,
            load_in_4bit=os.getenv("KAGAMI_USE_4BIT", "0") == "1",
            load_in_8bit=os.getenv("KAGAMI_USE_8BIT", "0") == "1",
        )

    return _structured_client


async def initialize_structured_client() -> None:
    """Initialize the global structured output client."""
    # Skip initialization in test echo mode
    if os.getenv("KAGAMI_TEST_ECHO_LLM", "0").lower() in ("1", "true", "yes"):
        logger.info("Skipping structured client initialization (test echo mode)")
        return

    client = get_structured_client()
    await client.initialize()


__all__ = [
    "StructuredOutputClient",
    "get_structured_client",
    "initialize_structured_client",
]
