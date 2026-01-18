"""Frozen LLM Service - Qwen for goal generation and world model alignment.

Uses the same frozen LLM (Qwen2.5-7B or compatible) that's used in
joint_llm_world_model training. Provides text generation for:
- Autonomous goal generation
- Action mapping
- Competence goal synthesis

ARCHITECTURE:
This service provides a singleton interface to the frozen LLM used in world model
training. The LLM is frozen (no gradients) and used for generation tasks only.

The same model weights are shared between:
1. World model training (joint_llm_world_model.py) - for E8 alignment
2. Goal generation (intrinsic_motivation.py) - for autonomous goals
3. Action mapping (intelligent_action_mapper.py) - for goal-to-action translation

MATHEMATICAL GROUNDING:
The frozen LLM serves as a fixed embedding space that:
1. Provides consistent semantic representations
2. Enables stable world model alignment (JEPA-style)
3. Generates coherent text descriptions
4. Maps goals to actions with linguistic understanding

SAFETY:
- All parameters are frozen (requires_grad=False)
- Read-only generation mode (no training)
- Memory-efficient (fp16 on GPU, fp32 on CPU)
"""

from __future__ import annotations

import logging
from typing import Any

import torch

logger = logging.getLogger(__name__)

# Global singleton
_frozen_llm_model: Any | None = None
_frozen_llm_tokenizer: Any | None = None
_frozen_llm_device: str = "cpu"


def get_frozen_llm_device() -> str:
    """Determine optimal device for frozen LLM.

    Returns:
        "cuda", "mps", or "cpu"
    """
    if torch.cuda.is_available():
        return "cuda"
    elif torch.backends.mps.is_available():
        return "mps"
    else:
        return "cpu"


def get_frozen_llm() -> tuple[Any, Any]:
    """Get or load frozen LLM for generation tasks.

    This uses the same model as joint_llm_world_model.py training,
    ensuring consistency between world model alignment and goal generation.

    Returns:
        (model, tokenizer) tuple[Any, ...]. If loading fails, returns (None, None).

    Example:
        >>> model, tokenizer = get_frozen_llm()
        >>> if model is not None:
        ...     prompt = "Generate a research question about octonions"
        ...     response = await generate_text(prompt)
    """
    global _frozen_llm_model, _frozen_llm_tokenizer, _frozen_llm_device

    if _frozen_llm_model is not None:
        return _frozen_llm_model, _frozen_llm_tokenizer

    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer

        # Use canonical model resolution from types.py
        from kagami.core.services.llm.types import get_default_model

        model_name = get_default_model()

        # Determine device
        _frozen_llm_device = get_frozen_llm_device()

        logger.info(f"Loading frozen LLM: {model_name} on {_frozen_llm_device}...")

        # Load tokenizer
        _frozen_llm_tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)

        # CRITICAL: Set padding_side='left' for decoder-only models (batch generation)
        # This ensures correct attention masking when generating for padded batches
        _frozen_llm_tokenizer.padding_side = "left"

        # Ensure pad token exists
        if _frozen_llm_tokenizer.pad_token is None:
            _frozen_llm_tokenizer.pad_token = _frozen_llm_tokenizer.eos_token

        logger.info("✅ Tokenizer loaded")

        # Load model with appropriate dtype
        torch_dtype = torch.float16 if _frozen_llm_device != "cpu" else torch.float32

        _frozen_llm_model = AutoModelForCausalLM.from_pretrained(
            model_name,
            torch_dtype=torch_dtype,
            device_map=None,  # Manual device management
            trust_remote_code=True,
        )

        # Move to device
        _frozen_llm_model = _frozen_llm_model.to(_frozen_llm_device)  # type: ignore[arg-type]
        logger.info(f"✅ LLM moved to {_frozen_llm_device}")

        # CRITICAL: Freeze all parameters
        for param in _frozen_llm_model.parameters():
            param.requires_grad = False

        _frozen_llm_model.eval()

        logger.info(
            f"✅ Frozen LLM loaded: {model_name} "
            f"({_frozen_llm_model.config.hidden_size}D embeddings, "
            f"{sum(p.numel() for p in _frozen_llm_model.parameters()):,} params)"
        )

        return _frozen_llm_model, _frozen_llm_tokenizer

    except Exception as e:
        logger.error(f"Failed to load frozen LLM: {e}")
        return None, None


async def generate_text(
    prompt: str,
    max_tokens: int = 200,
    temperature: float = 0.8,
    top_p: float = 0.9,
    do_sample: bool = True,
) -> str | None:
    """Generate text using frozen LLM.

    Args:
        prompt: Input prompt
        max_tokens: Maximum tokens to generate
        temperature: Sampling temperature (0.0 = deterministic, 1.0 = creative)
        top_p: Nucleus sampling threshold
        do_sample: Whether to use sampling (True) or greedy decoding (False)

    Returns:
        Generated text (without prompt), or None if LLM unavailable

    Example:
        >>> prompt = "You are an AI generating research questions. Question:"
        >>> response = await generate_text(prompt, max_tokens=100, temperature=0.8)
        >>> print(response)
        "How do octonions relate to exceptional Lie algebras?"
    """
    model, tokenizer = get_frozen_llm()

    if model is None or tokenizer is None:
        logger.warning("Frozen LLM not available for generation")
        return None

    try:
        # Tokenize
        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

        # Generate with no gradients
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=max_tokens,
                temperature=temperature if do_sample else 1.0,
                do_sample=do_sample,
                top_p=top_p if do_sample else 1.0,
                pad_token_id=tokenizer.pad_token_id,
                eos_token_id=tokenizer.eos_token_id,
            )

        # Decode
        generated = tokenizer.decode(outputs[0], skip_special_tokens=True)

        # Remove prompt from output
        response = generated[len(prompt) :].strip()
        return response  # type: ignore[no-any-return]

    except Exception as e:
        logger.error(f"Text generation failed: {e}")
        return None


async def batch_generate_text(
    prompts: list[str],
    max_tokens: int = 200,
    temperature: float = 0.8,
    top_p: float = 0.9,
    do_sample: bool = True,
) -> list[str | None]:
    """Generate text for multiple prompts in batch.

    More efficient than calling generate_text() multiple times.

    Args:
        prompts: List of input prompts
        max_tokens: Maximum tokens per generation
        temperature: Sampling temperature
        top_p: Nucleus sampling threshold
        do_sample: Whether to use sampling

    Returns:
        List of generated texts (one per prompt), None for failed generations

    Example:
        >>> prompts = [
        ...     "Research question about physics:",
        ...     "Research question about math:",
        ... ]
        >>> responses = await batch_generate_text(prompts, max_tokens=50)
        >>> for response in responses:
        ...     print(response)
    """
    model, tokenizer = get_frozen_llm()

    if model is None or tokenizer is None:
        logger.warning("Frozen LLM not available for batch generation")
        return [None] * len(prompts)

    try:
        # Tokenize batch
        inputs = tokenizer(
            prompts,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=512,
        ).to(model.device)

        # Generate batch with no gradients
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=max_tokens,
                temperature=temperature if do_sample else 1.0,
                do_sample=do_sample,
                top_p=top_p if do_sample else 1.0,
                pad_token_id=tokenizer.pad_token_id,
                eos_token_id=tokenizer.eos_token_id,
            )

        # Decode batch
        responses: list[str | None] = []
        for i, output in enumerate(outputs):
            generated = tokenizer.decode(output, skip_special_tokens=True)
            # Remove prompt from output
            response = generated[len(prompts[i]) :].strip()
            responses.append(response)

        return responses

    except Exception as e:
        logger.error(f"Batch text generation failed: {e}")
        return [None] * len(prompts)


def is_frozen_llm_available() -> bool:
    """Check if frozen LLM is loaded and ready.

    Returns:
        True if model is loaded, False otherwise
    """
    return _frozen_llm_model is not None and _frozen_llm_tokenizer is not None


def get_frozen_llm_stats() -> dict[str, Any]:
    """Get statistics about the frozen LLM.

    Returns:
        Dictionary with model statistics
    """
    if not is_frozen_llm_available():
        return {
            "loaded": False,
            "device": _frozen_llm_device,
        }

    model, tokenizer = get_frozen_llm()

    stats = {
        "loaded": True,
        "device": _frozen_llm_device,
        "hidden_size": model.config.hidden_size,
        "vocab_size": tokenizer.vocab_size,
        "num_parameters": sum(p.numel() for p in model.parameters()),
        "frozen_parameters": sum(p.numel() for p in model.parameters() if not p.requires_grad),
        "trainable_parameters": sum(p.numel() for p in model.parameters() if p.requires_grad),
    }

    return stats


class FrozenLLMService:
    """Service wrapper for frozen LLM with synchronous interface.

    Provides a simple synchronous interface to the frozen LLM for
    code that can't easily use async/await.
    """

    def __init__(self) -> None:
        """Initialize frozen LLM service."""
        pass

    async def generate(
        self,
        prompt: str,
        max_tokens: int = 200,
        temperature: float = 0.8,
    ) -> str:
        """Generate text using frozen LLM.

        Args:
            prompt: Input prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            Generated text
        """
        result = await generate_text(prompt, max_tokens=max_tokens, temperature=temperature)
        return result or ""


_frozen_llm_service_singleton: FrozenLLMService | None = None


def get_frozen_llm_service() -> FrozenLLMService:
    """Get the global frozen LLM service instance.

    Returns:
        FrozenLLMService instance
    """
    global _frozen_llm_service_singleton
    if _frozen_llm_service_singleton is None:
        _frozen_llm_service_singleton = FrozenLLMService()
    return _frozen_llm_service_singleton


__all__ = [
    "FrozenLLMService",
    "batch_generate_text",
    "generate_text",
    "get_frozen_llm",
    "get_frozen_llm_device",
    "get_frozen_llm_service",
    "get_frozen_llm_stats",
    "is_frozen_llm_available",
]
