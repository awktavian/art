from __future__ import annotations

"""Enhanced Structured JSON generation with advanced constrained decoding.

This module extends the basic structured generation with:
- Grammar-constrained decoding enabled by default
- Dynamic fallback to grammar constraints on failure
- Error-aware prompting with validation hints
- Advanced JSON repair strategies
- Multi-step reasoning with scratchpad mode
- Semantic validation beyond Pydantic
- Incremental field-by-field generation
- User feedback collection

Based on state-of-the-art research and best practices from:
- Outlines, Guidance, XGrammar for constrained decoding
- IterGen for iterative refinement
- "Think Inside the JSON" for RL-based schema adherence
"""
import asyncio
import json
import logging
import os
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

torch: Any = None
_TORCH_AVAILABLE = False
try:
    import torch as _torch

    torch = _torch
    _TORCH_AVAILABLE = True
except (ImportError, ModuleNotFoundError) as e:
    logger.debug(f"torch not available, structured features may be limited: {e}")
    # Optional dependency - torch not required for basic structured generation

_STRUCT_ENHANCED_TOTAL: Any = None
_STRUCT_REPAIR_TOTAL: Any = None
_STRUCT_GRAMMAR_TOTAL: Any = None
_STRUCT_FEEDBACK_TOTAL: Any = None

try:
    from kagami_observability.metrics import REGISTRY
    from prometheus_client import Counter

    _STRUCT_ENHANCED_TOTAL = Counter(
        "kagami_structured_enhanced_total",
        "Enhanced structured generation outcomes",
        ["model", "outcome", "strategy"],
        registry=REGISTRY,
    )
    _STRUCT_REPAIR_TOTAL = Counter(
        "kagami_structured_repair_total",
        "JSON repair attempts and outcomes",
        ["repair_type", "outcome"],
        registry=REGISTRY,
    )
    _STRUCT_GRAMMAR_TOTAL = Counter(
        "kagami_structured_grammar_total",
        "Grammar-constrained generation usage",
        ["enabled", "outcome"],
        registry=REGISTRY,
    )
    _STRUCT_FEEDBACK_TOTAL = Counter(
        "kagami_structured_feedback_total",
        "User feedback on structured outputs",
        ["rating", "schema_type"],
        registry=REGISTRY,
    )
except (ImportError, ModuleNotFoundError) as e:
    logger.debug(
        f"Prometheus metrics not available, structured generation will run without metrics: {e}"
    )
    # Optional dependency - metrics enhance observability but aren't required

T = TypeVar("T", bound=BaseModel)

# ---------------------------------------------------------------------------
# Minimal local HF helpers (avoid dependence on legacy llm_structured module)
# ---------------------------------------------------------------------------


def _select_device() -> str:
    try:
        if _TORCH_AVAILABLE and getattr(torch, "backends", None):
            if getattr(torch, "cuda", None) and torch.cuda.is_available():
                return "cuda"
            if torch.backends.mps.is_available():
                return "mps"
    except (AttributeError, RuntimeError) as e:
        logger.debug(f"Device detection failed, falling back to CPU: {e}")
        # Expected in environments without GPU/MPS support
    return "cpu"


async def _hf_generate_simple(
    prompt: str,
    model_name: str | None,
    temperature: float,
    max_tokens: int,
    device: str | None = None,
) -> str:
    """Lightweight local generation using transformers with safe defaults."""
    try:
        import torch as _torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        name = (  # type: ignore  # Union member
            model_name
            or os.getenv("KAGAMI_TRANSFORMERS_MODEL_FAST", "Qwen/Qwen3-1.7B")  # Cached locally
        ).strip()
        device_sel = device or _select_device()

        tokenizer = AutoTokenizer.from_pretrained(name, trust_remote_code=False)
        tokenizer.padding_side = "left"  # Decoder-only batch fix
        model = AutoModelForCausalLM.from_pretrained(
            name,
            torch_dtype=(_torch.float16 if device_sel in ("cuda", "mps") else _torch.float32),
            trust_remote_code=False,
        )
        if device_sel != "cpu":
            model = model.to(device_sel)  # type: ignore[arg-type]

        inputs = tokenizer(prompt, return_tensors="pt")
        if device_sel != "cpu":
            inputs = {k: v.to(device_sel) for k, v in inputs.items()}

        gen_kwargs = {
            "max_new_tokens": int(max(1, max_tokens)),
            "temperature": float(max(0.0, temperature)),
            "do_sample": temperature > 0.0,
            "eos_token_id": getattr(tokenizer, "eos_token_id", None),
        }
        with _torch.no_grad():
            output = model.generate(**inputs, **gen_kwargs)  # type: ignore[arg-type]
        text = tokenizer.decode(output[0], skip_special_tokens=True)
        return str(text.strip())
    except Exception as e:
        logger.error(f"HF generation failed: {e}")
        raise


class GenerationStrategy(str, Enum):
    """Strategy for structured generation."""

    PROMPT_ONLY = "prompt_only"
    GRAMMAR_CONSTRAINED = "grammar_constrained"
    FUNCTION_CALLING = "function_calling"
    SCRATCHPAD_REASONING = "scratchpad_reasoning"
    INCREMENTAL_FIELDS = "incremental_fields"


class RepairStrategy(str, Enum):
    """Strategy for repairing invalid JSON."""

    REGEX_FIXES = "regex_fixes"
    TOLERANT_PARSER = "tolerant_parser"
    LLM_CORRECTION = "llm_correction"
    FIELD_DEFAULTS = "field_defaults"


@dataclass
class GenerationResult:
    """Result of a structured generation attempt."""

    success: bool
    data: dict[str, Any] | None
    strategy_used: GenerationStrategy
    repair_applied: RepairStrategy | None = None
    attempts: int = 1
    error: str | None = None
    reasoning_trace: str | None = None
    validation_feedback: dict[str, Any] | None = None


@dataclass
class UserFeedback:
    """User feedback on generated output."""

    correlation_id: str
    schema_type: str
    rating: int  # 1-5
    corrected_output: dict[str, Any] | None = None
    comments: str | None = None
    timestamp: float = field(default_factory=time.time)


class JSONRepairModule:
    """Advanced JSON repair strategies."""

    @staticmethod
    def regex_repairs(text: str) -> str | None:
        """Apply regex-based repairs for common JSON issues."""
        if not text:
            return None

        try:
            # Remove trailing commas
            text = re.sub(r",\s*}", "}", text)
            text = re.sub(r",\s*]", "]", text)

            # Fix single quotes to double quotes (careful with apostrophes)
            text = re.sub(r"(?<![a-zA-Z])'([^']*)'(?![a-zA-Z])", r'"\1"', text)

            # Fix unquoted keys (simple cases)
            text = re.sub(r"(\w+):", r'"\1":', text)

            # Remove comments
            text = re.sub(r"//.*$", "", text, flags=re.MULTILINE)
            text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)

            # Try to parse
            json.loads(text)
            if _STRUCT_REPAIR_TOTAL:
                _STRUCT_REPAIR_TOTAL.labels("regex_fixes", "success").inc()
            return text
        except (json.JSONDecodeError, ValueError) as e:
            logger.debug(f"Regex repair failed to produce valid JSON: {e}")
            if _STRUCT_REPAIR_TOTAL:
                _STRUCT_REPAIR_TOTAL.labels("regex_fixes", "failed").inc()
            return None

    @staticmethod
    def tolerant_parse(text: str) -> dict[str, Any] | None:
        """Use tolerant parsing to extract JSON."""
        try:
            # Try json5 if available (more lenient)
            try:
                import json5

                data = json5.loads(text)
                if _STRUCT_REPAIR_TOTAL:
                    _STRUCT_REPAIR_TOTAL.labels("tolerant_parser", "success").inc()
                return dict(data) if isinstance(data, dict) else None
            except ImportError as e:
                logger.debug(
                    f"json5 library not available, falling back to standard JSON parsing: {e}"
                )
                # Optional dependency - json5 provides more lenient parsing

            # Fallback to extracting JSON-like structure
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                snippet = text[start : end + 1]
                # Apply regex repairs first
                repaired = JSONRepairModule.regex_repairs(snippet)
                if repaired:
                    return (
                        dict(json.loads(repaired))
                        if isinstance(json.loads(repaired), dict)
                        else None
                    )
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.debug(f"Tolerant parse failed: {e}")
            # Expected when JSON is too malformed for repair strategies

        if _STRUCT_REPAIR_TOTAL:
            _STRUCT_REPAIR_TOTAL.labels("tolerant_parser", "failed").inc()
        return None


class SemanticValidator:
    """Domain-specific semantic validation beyond Pydantic."""

    @staticmethod
    async def validate_timeline(data: dict[str, Any]) -> tuple[bool, list[str]]:
        """Validate timeline/schedule semantics."""
        errors: list[Any] = []

        # Check date ordering
        if "start_date" in data and "end_date" in data:
            try:
                from datetime import datetime

                start = datetime.fromisoformat(data["start_date"])
                end = datetime.fromisoformat(data["end_date"])
                if start > end:
                    errors.append("Start date must be before end date")
            except (ValueError, TypeError) as e:
                logger.debug(f"Date parsing failed during timeline validation: {e}")
                # Expected for invalid date formats - skip this validation check

        # Check phase ordering
        if "phases" in data and isinstance(data["phases"], list):
            for i, phase in enumerate(data["phases"]):
                if i > 0 and "start" in phase and "start" in data["phases"][i - 1]:
                    try:
                        if phase["start"] < data["phases"][i - 1]["start"]:
                            errors.append(f"Phase {i} starts before phase {i - 1}")
                    except (KeyError, TypeError, ValueError) as e:
                        logger.debug(f"Phase ordering check failed for phase {i}: {e}")
                        # Expected when phase data is incomplete or malformed

        return len(errors) == 0, errors

    @staticmethod
    async def validate_financial(data: dict[str, Any]) -> tuple[bool, list[str]]:
        """Validate financial data semantics."""
        errors: list[Any] = []

        # Check amount ranges
        for amount_field in ["amount", "total", "price"]:
            if amount_field in data:
                try:
                    value = float(data[amount_field])
                    if value < 0:
                        errors.append(f"{amount_field} cannot be negative")
                    if value > 1e12:  # Trillion dollar check
                        errors.append(f"{amount_field} seems unreasonably large")
                except (ValueError, TypeError) as e:
                    logger.debug(f"Amount validation failed for {amount_field}: {e}")
                    # Expected when amount field is not numeric

        # Check percentage ranges
        for percent_field in ["percentage", "rate", "discount"]:
            if percent_field in data:
                try:
                    value = float(data[percent_field])
                    if value < 0 or value > 100:
                        errors.append(f"{percent_field} should be between 0 and 100")
                except (ValueError, TypeError) as e:
                    logger.debug(f"Percentage validation failed for {percent_field}: {e}")
                    # Expected when percentage field is not numeric

        return len(errors) == 0, errors


class EnhancedStructuredGenerator:
    """Enhanced structured generation with advanced strategies."""

    def __init__(self) -> None:
        self.repair_module = JSONRepairModule()
        self.semantic_validator = SemanticValidator()
        self.feedback_store: list[UserFeedback] = []
        self.generation_history: dict[str, list[GenerationResult]] = defaultdict(list[Any])

    async def generate_with_strategy(
        self,
        model_name: str | None,
        pydantic_model: type[T],
        system_prompt: str,
        user_prompt: str,
        strategy: GenerationStrategy = GenerationStrategy.GRAMMAR_CONSTRAINED,
        temperature: float = 0.2,
        max_tokens: int = 512,
        timeout_s: float = 8.0,
        max_attempts: int = 3,
        enable_semantic_validation: bool = True,
        enable_scratchpad: bool = False,
        images: list[str] | None = None,
        audio: list[str] | None = None,
    ) -> T:
        """Generate structured output with advanced strategies."""

        # Track generation attempt
        f"gen_{time.time():.0f}_{os.getpid()}"
        schema_name = pydantic_model.__name__

        # Try primary strategy first
        result = await self._attempt_generation(
            model_name=model_name,
            pydantic_model=pydantic_model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            strategy=strategy,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout_s=timeout_s,
            enable_scratchpad=enable_scratchpad,
            images=images,
            audio=audio,
        )

        # If failed, try fallback strategies
        if not result.success and max_attempts > 1:
            fallback_strategies = self._get_fallback_strategies(strategy)

            for fallback_strategy in fallback_strategies[: max_attempts - 1]:
                # Add error hints to prompt
                enhanced_prompt = self._add_error_hints(
                    user_prompt, result.error, result.validation_feedback
                )

                result = await self._attempt_generation(
                    model_name=model_name,
                    pydantic_model=pydantic_model,
                    system_prompt=system_prompt,
                    user_prompt=enhanced_prompt,
                    strategy=fallback_strategy,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout_s=timeout_s,
                    enable_scratchpad=True,  # Enable scratchpad on retry
                    images=images,
                    audio=audio,
                )

                if result.success:
                    break

        # Store result in history
        self.generation_history[schema_name].append(result)

        # Convert to Pydantic model
        if result.success and result.data:
            try:
                instance = pydantic_model.model_validate(result.data)

                # Semantic validation if enabled
                if enable_semantic_validation:
                    await self._semantic_validation(instance, schema_name)

                # Track success metrics
                if _STRUCT_ENHANCED_TOTAL:
                    _STRUCT_ENHANCED_TOTAL.labels(
                        model_name or "default", "success", result.strategy_used.value
                    ).inc()

                return instance

            except ValidationError as e:
                result.success = False
                result.error = str(e)

        # K2 Full Operation Mode: Fail explicitly when all strategies fail
        # No degraded mode - surface clear error with recovery guidance
        logger.error(f"All strategies failed for {schema_name}")

        # Track failure metrics
        if _STRUCT_ENHANCED_TOTAL:
            _STRUCT_ENHANCED_TOTAL.labels(
                model_name or "default", "failed", result.strategy_used.value
            ).inc()

        raise RuntimeError(
            f"Structured generation failed for {schema_name}. "
            f"All {max_attempts} attempts exhausted. "
            f"Tried strategies: {[s.value for s in [GenerationStrategy.GRAMMAR_CONSTRAINED, GenerationStrategy.JSON_REPAIR]]}. "  # type: ignore  # Dynamic attr
            f"Last error: {result.error or 'unknown'}. "
            f"Hint: Ensure language model is available and responsive."
        )

    async def _attempt_generation(
        self,
        model_name: str | None,
        pydantic_model: type[BaseModel],
        system_prompt: str,
        user_prompt: str,
        strategy: GenerationStrategy,
        temperature: float,
        max_tokens: int,
        timeout_s: float,
        enable_scratchpad: bool,
        images: list[str] | None,
        audio: list[str] | None,
    ) -> GenerationResult:
        """Attempt generation with a specific strategy."""

        try:
            if strategy == GenerationStrategy.GRAMMAR_CONSTRAINED:
                return await self._grammar_constrained_generation(
                    model_name,
                    pydantic_model,
                    system_prompt,
                    user_prompt,
                    temperature,
                    max_tokens,
                    timeout_s,
                    images,
                    audio,
                )
            elif strategy == GenerationStrategy.SCRATCHPAD_REASONING:
                return await self._scratchpad_generation(
                    model_name,
                    pydantic_model,
                    system_prompt,
                    user_prompt,
                    temperature,
                    max_tokens,
                    timeout_s,
                    images,
                    audio,
                )
            elif strategy == GenerationStrategy.INCREMENTAL_FIELDS:
                return await self._incremental_generation(
                    model_name,
                    pydantic_model,
                    system_prompt,
                    user_prompt,
                    temperature,
                    max_tokens,
                    timeout_s,
                    images,
                    audio,
                )
            elif strategy == GenerationStrategy.FUNCTION_CALLING:
                return await self._function_calling_generation(
                    model_name,
                    pydantic_model,
                    system_prompt,
                    user_prompt,
                    temperature,
                    max_tokens,
                    timeout_s,
                    images,
                    audio,
                )
            else:
                # Default to prompt-only
                return await self._prompt_only_generation(
                    model_name,
                    pydantic_model,
                    system_prompt,
                    user_prompt,
                    temperature,
                    max_tokens,
                    timeout_s,
                    images,
                    audio,
                )
        except Exception as e:
            logger.error(f"Generation failed with {strategy}: {e}")
            return GenerationResult(success=False, data=None, strategy_used=strategy, error=str(e))

    async def _grammar_constrained_generation(
        self,
        model_name: str | None,
        pydantic_model: type[BaseModel],
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
        timeout_s: float,
        images: list[str] | None,
        audio: list[str] | None,
    ) -> GenerationResult:
        """Generate with grammar constraints using Outlines directly."""

        try:
            import importlib

            outlines_models = importlib.import_module("outlines.models")
            outlines_generate = importlib.import_module("outlines.generate")

            # Prepare schema
            try:
                schema_obj = pydantic_model.model_json_schema()
            except Exception:
                schema_obj = {"type": "object"}

            # Build model wrapper (pass id or model object)
            device = _select_device()
            try:
                ol_model = outlines_models.transformers(
                    model_name
                    or os.getenv("KAGAMI_TRANSFORMERS_MODEL_FAST", "Qwen/Qwen3-1.7B"),  # Cached
                    device=device,
                )
            except (TypeError, ValueError) as e:
                logger.debug(
                    f"Outlines model creation with device failed, trying without device param: {e}"
                )
                # Some outlines versions don't support device parameter
                ol_model = outlines_models.transformers(
                    model_name
                    or os.getenv("KAGAMI_TRANSFORMERS_MODEL_FAST", "Qwen/Qwen3-1.7B")  # Cached
                )

            ol_json_factory = getattr(outlines_generate, "json", None)
            if not callable(ol_json_factory):
                raise RuntimeError("outlines.generate.json not callable") from None

            generator = ol_json_factory(ol_model, schema_obj)

            async def _gen() -> str:
                return await asyncio.to_thread(
                    generator, f"{system_prompt.strip()}\n\n{user_prompt.strip()}"
                )

            text = await asyncio.wait_for(_gen(), timeout=max(0.1, timeout_s))
            # Extract JSON
            start = text.find("{")
            end = text.rfind("}")
            if start < 0 or end <= start:
                raise ValueError("No JSON found in constrained output")
            data = json.loads(text[start : end + 1])

            if _STRUCT_GRAMMAR_TOTAL:
                _STRUCT_GRAMMAR_TOTAL.labels("true", "success").inc()

            return GenerationResult(
                success=True,
                data=data,
                strategy_used=GenerationStrategy.GRAMMAR_CONSTRAINED,
            )
        except Exception as e:
            if _STRUCT_GRAMMAR_TOTAL:
                _STRUCT_GRAMMAR_TOTAL.labels("true", "failed").inc()
            return GenerationResult(
                success=False,
                data=None,
                strategy_used=GenerationStrategy.GRAMMAR_CONSTRAINED,
                error=str(e),
            )

    async def _scratchpad_generation(
        self,
        model_name: str | None,
        pydantic_model: type[BaseModel],
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
        timeout_s: float,
        images: list[str] | None,
        audio: list[str] | None,
    ) -> GenerationResult:
        """Two-phase generation with reasoning scratchpad."""

        # Phase 1: Reasoning
        reasoning_prompt = f"""
{system_prompt}

First, think through the requirements step by step. List the key fields needed and their values.
Then, provide your final answer as a JSON object.

User request: {user_prompt}

Begin your reasoning with "REASONING:" and your JSON with "JSON:".
"""

        # Generate with higher temperature for reasoning
        try:
            full_response = await _hf_generate_simple(
                prompt=reasoning_prompt,
                model_name=model_name,
                temperature=temperature * 1.5,
                max_tokens=max_tokens * 2,
                device=_select_device(),
            )

            # Extract reasoning and JSON
            reasoning_trace = ""
            json_text = ""

            if "REASONING:" in full_response:
                parts = full_response.split("REASONING:", 1)
                if len(parts) > 1:
                    reasoning_part = parts[1]
                    if "JSON:" in reasoning_part:
                        reasoning_trace, json_text = reasoning_part.split("JSON:", 1)
                    else:
                        reasoning_trace = reasoning_part

            # Try to extract JSON
            if not json_text and "{" in full_response:
                start = full_response.find("{")
                end = full_response.rfind("}")
                if start >= 0 and end > start:
                    json_text = full_response[start : end + 1]

            # Parse and validate
            if json_text:
                # Try repair if needed
                data = self.repair_module.tolerant_parse(json_text)
                if not data:
                    data = json.loads(self.repair_module.regex_repairs(json_text) or "{}")

                # Validate with Pydantic
                instance = pydantic_model.model_validate(data)

                return GenerationResult(
                    success=True,
                    data=instance.model_dump(),
                    strategy_used=GenerationStrategy.SCRATCHPAD_REASONING,
                    reasoning_trace=reasoning_trace,
                )
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.debug(f"Scratchpad generation parsing failed: {e}")
            # Expected when model doesn't follow scratchpad format

        return GenerationResult(
            success=False,
            data=None,
            strategy_used=GenerationStrategy.SCRATCHPAD_REASONING,
            error="Scratchpad generation failed",
        )

    async def _incremental_generation(
        self,
        model_name: str | None,
        pydantic_model: type[BaseModel],
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
        timeout_s: float,
        images: list[str] | None,
        audio: list[str] | None,
    ) -> GenerationResult:
        """Generate complex schemas field by field."""

        # Get schema fields
        try:
            schema = pydantic_model.model_json_schema()
            properties = schema.get("properties", {})
            required = schema.get("required", [])
        except (AttributeError, ValueError) as e:
            logger.warning(f"Schema extraction failed for incremental generation: {e}")
            properties: dict[str, Any] = {}  # type: ignore  # Redef
            required: list[Any] = []  # type: ignore  # Redef
            # Fallback when pydantic model introspection fails

        if not properties:
            # Fall back to regular generation
            return await self._prompt_only_generation(
                model_name,
                pydantic_model,
                system_prompt,
                user_prompt,
                temperature,
                max_tokens,
                timeout_s,
                images,
                audio,
            )

        # Generate each field incrementally
        result_data: dict[str, Any] = {}
        context = f"{system_prompt}\n\nUser request: {user_prompt}\n\n"

        for field_name, field_schema in properties.items():
            # Create a simple schema for this field
            class SingleField(BaseModel):
                value: Any

            field_prompt = f"""
{context}
Previous fields generated: {json.dumps(result_data, indent=2)}

Now generate the value for field "{field_name}".
Field schema: {json.dumps(field_schema)}
Required: {field_name in required}

Return JSON with "value" key containing the field value.
"""

            try:
                # Prefer constrained generation per-field for correctness
                sub_inst = await generate_structured_enhanced(
                    model_name=model_name,
                    pydantic_model=SingleField,
                    system_prompt="Return only JSON with key 'value' per schema.",
                    user_prompt=field_prompt,
                    strategy=GenerationStrategy.GRAMMAR_CONSTRAINED,
                    temperature=temperature,
                    max_tokens=max(32, max_tokens // max(1, len(properties))),
                    timeout_s=max(1.0, timeout_s / max(1, len(properties))),
                    max_attempts=1,
                )
                result_data[field_name] = getattr(sub_inst, "value", None)
            except (RuntimeError, ValidationError) as e:
                # Field generation failed
                logger.debug(f"Field generation failed for {field_name}: {e}")
                if field_name not in required:
                    continue
                else:
                    # Critical field failed
                    return GenerationResult(
                        success=False,
                        data=result_data,
                        strategy_used=GenerationStrategy.INCREMENTAL_FIELDS,
                        error=f"Failed to generate required field {field_name}",
                    )

        # Validate complete result
        try:
            instance = pydantic_model.model_validate(result_data)
            return GenerationResult(
                success=True,
                data=instance.model_dump(),
                strategy_used=GenerationStrategy.INCREMENTAL_FIELDS,
            )
        except Exception as e:
            return GenerationResult(
                success=False,
                data=result_data,
                strategy_used=GenerationStrategy.INCREMENTAL_FIELDS,
                error=str(e),
            )

    async def _function_calling_generation(
        self,
        model_name: str | None,
        pydantic_model: type[BaseModel],
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
        timeout_s: float,
        images: list[str] | None,
        audio: list[str] | None,
    ) -> GenerationResult:
        """Use OpenAI function calling for structured output."""

        # Check if we can use OpenAI
        if not os.getenv("OPENAI_API_KEY"):
            return GenerationResult(
                success=False,
                data=None,
                strategy_used=GenerationStrategy.FUNCTION_CALLING,
                error="OpenAI API key not available",
            )

        try:
            import openai

            client = openai.AsyncOpenAI()

            # Convert Pydantic schema to OpenAI function schema
            schema = pydantic_model.model_json_schema()

            function_def = {
                "name": "generate_structured",
                "description": f"Generate {pydantic_model.__name__}",
                "parameters": schema,
            }

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            # Add images if provided
            if images:
                # Encode images as base64 for vision models
                import base64

                for img_path in images[:1]:  # Use first image only for now
                    with open(img_path, "rb") as f:
                        img_data = base64.b64encode(f.read()).decode()
                        messages[-1]["content"] = [  # type: ignore[assignment]
                            {"type": "text", "text": user_prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/jpeg;base64,{img_data}"},
                            },
                        ]

            response = await client.chat.completions.create(  # type: ignore  # Overload call
                model=model_name or "gpt-4-turbo-preview",
                messages=messages,
                functions=[function_def],
                function_call={"name": "generate_structured"},
                temperature=temperature,
                max_tokens=max_tokens,
            )

            # Extract function call arguments
            if response.choices[0].message.function_call:
                args_str = response.choices[0].message.function_call.arguments
                data = json.loads(args_str)

                # Validate with Pydantic
                instance = pydantic_model.model_validate(data)

                return GenerationResult(
                    success=True,
                    data=instance.model_dump(),
                    strategy_used=GenerationStrategy.FUNCTION_CALLING,
                )
        except Exception as e:
            logger.error(f"Function calling failed: {e}")

        return GenerationResult(
            success=False,
            data=None,
            strategy_used=GenerationStrategy.FUNCTION_CALLING,
            error="Function calling generation failed",
        )

    async def _prompt_only_generation(
        self,
        model_name: str | None,
        pydantic_model: type[BaseModel],
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
        timeout_s: float,
        images: list[str] | None,
        audio: list[str] | None,
    ) -> GenerationResult:
        """Basic prompt-based generation (unconstrained)."""

        try:
            text = await _hf_generate_simple(
                prompt=f"{system_prompt.strip()}\n\n{user_prompt.strip()}",
                model_name=model_name,
                temperature=temperature,
                max_tokens=max_tokens,
                device=_select_device(),
            )
            # Extract JSON
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                snippet = text[start : end + 1]
                try:
                    data = json.loads(snippet)
                except Exception:
                    # Attempt repair
                    repaired = self.repair_module.regex_repairs(snippet)
                    data = json.loads(repaired) if repaired else {}
            else:
                # Try tolerant parse of full text
                data = self.repair_module.tolerant_parse(text) or {}

            instance = pydantic_model.model_validate(data)
            return GenerationResult(
                success=True,
                data=instance.model_dump(),
                strategy_used=GenerationStrategy.PROMPT_ONLY,
            )
        except Exception as e:
            return GenerationResult(
                success=False,
                data=None,
                strategy_used=GenerationStrategy.PROMPT_ONLY,
                error=str(e),
            )

    def _get_fallback_strategies(self, primary: GenerationStrategy) -> list[GenerationStrategy]:
        """Get fallback strategies based on primary strategy."""

        if primary == GenerationStrategy.PROMPT_ONLY:
            return [
                GenerationStrategy.GRAMMAR_CONSTRAINED,
                GenerationStrategy.SCRATCHPAD_REASONING,
                GenerationStrategy.FUNCTION_CALLING,
            ]
        elif primary == GenerationStrategy.GRAMMAR_CONSTRAINED:
            return [
                GenerationStrategy.SCRATCHPAD_REASONING,
                GenerationStrategy.INCREMENTAL_FIELDS,
                GenerationStrategy.FUNCTION_CALLING,
            ]
        elif primary == GenerationStrategy.SCRATCHPAD_REASONING:
            return [
                GenerationStrategy.GRAMMAR_CONSTRAINED,
                GenerationStrategy.INCREMENTAL_FIELDS,
            ]
        else:
            return [
                GenerationStrategy.GRAMMAR_CONSTRAINED,
                GenerationStrategy.SCRATCHPAD_REASONING,
            ]

    def _add_error_hints(
        self, prompt: str, error: str | None, validation_feedback: dict[str, Any] | None
    ) -> str:
        """Add error hints to prompt for next attempt."""

        hints: list[Any] = []

        if error:
            if "JSONDecodeError" in error:
                hints.append(
                    "Ensure your output is valid JSON with proper quotes and no trailing commas."
                )
            elif "ValidationError" in error:
                # Parse validation error for specific fields
                if "field required" in error.lower():
                    hints.append("Make sure to include all required fields.")
                if "type" in error.lower():
                    hints.append(
                        "Check that field types match the schema (strings, numbers, etc.)."
                    )
            elif "timeout" in error.lower():
                hints.append("Generate a more concise response.")

        if validation_feedback:
            for field_name, feedback in validation_feedback.items():
                if isinstance(feedback, str):
                    hints.append(f"Field '{field_name}': {feedback}")

        if hints:
            hint_text = "\n\nIMPORTANT HINTS FOR THIS ATTEMPT:\n" + "\n".join(
                f"- {hint}" for hint in hints
            )
            return prompt + hint_text

        return prompt

    async def _semantic_validation(self, instance: BaseModel, schema_name: str) -> None:
        """Perform semantic validation based on schema type."""

        data = instance.model_dump()

        # Route to appropriate validator
        if "timeline" in schema_name.lower() or "schedule" in schema_name.lower():
            valid, errors = await self.semantic_validator.validate_timeline(data)
            if not valid:
                logger.warning(f"Semantic validation issues in {schema_name}: {errors}")
        elif "financial" in schema_name.lower() or "payment" in schema_name.lower():
            valid, errors = await self.semantic_validator.validate_financial(data)
            if not valid:
                logger.warning(f"Semantic validation issues in {schema_name}: {errors}")

    async def collect_feedback(
        self,
        correlation_id: str,
        schema_type: str,
        rating: int,
        corrected_output: dict[str, Any] | None = None,
        comments: str | None = None,
    ) -> None:
        """Collect user feedback on generated output."""

        feedback = UserFeedback(
            correlation_id=correlation_id,
            schema_type=schema_type,
            rating=rating,
            corrected_output=corrected_output,
            comments=comments,
        )

        self.feedback_store.append(feedback)

        # Track in metrics
        if _STRUCT_FEEDBACK_TOTAL:
            _STRUCT_FEEDBACK_TOTAL.labels(str(rating), schema_type).inc()

        # If we have enough feedback, consider triggering fine-tuning
        if len(self.feedback_store) >= 100:
            await self._prepare_finetuning_data()

    async def _prepare_finetuning_data(self) -> None:
        """Prepare fine-tuning dataset from feedback."""

        # Group feedback by schema type
        by_schema = defaultdict(list[Any])
        for fb in self.feedback_store:
            if fb.corrected_output and fb.rating <= 2:  # Poor ratings with corrections
                by_schema[fb.schema_type].append(fb)

        # Create training examples
        training_data: list[Any] = []
        for schema_type, feedbacks in by_schema.items():
            for fb in feedbacks:
                training_data.append(
                    {
                        "prompt": f"Generate {schema_type}",
                        "completion": json.dumps(fb.corrected_output),
                        "rating": fb.rating,
                    }
                )

        # Save for later fine-tuning
        if training_data:
            output_path = f"artifacts/finetuning/structured_{time.time():.0f}.jsonl"
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            with open(output_path, "w") as f:
                for example in training_data:
                    f.write(json.dumps(example) + "\n")

            logger.info(f"Saved {len(training_data)} fine-tuning examples to {output_path}")

            # Clear processed feedback
            self.feedback_store.clear()


# Global instance for easy access
_enhanced_generator = None


def get_enhanced_generator() -> EnhancedStructuredGenerator:
    """Get or create the global enhanced generator instance."""
    global _enhanced_generator
    if _enhanced_generator is None:
        _enhanced_generator = EnhancedStructuredGenerator()
    return _enhanced_generator


async def generate_structured_enhanced(
    model_name: str | None,
    pydantic_model: type[T],
    system_prompt: str,
    user_prompt: str,
    strategy: str | GenerationStrategy = "auto",
    temperature: float = 0.2,
    max_tokens: int = 512,
    timeout_s: float = 8.0,
    max_attempts: int = 3,
    enable_semantic_validation: bool = True,
    enable_scratchpad: bool = False,
    images: list[str] | None = None,
    audio: list[str] | None = None,
) -> T:
    """
    Enhanced structured generation with advanced features.

    Args:
        model_name: Model to use (None for auto-selection)
        pydantic_model: Pydantic model for validation
        system_prompt: System instructions
        user_prompt: User request
        strategy: Generation strategy ("auto" for smart selection)
        temperature: Sampling temperature
        max_tokens: Maximum tokens to generate
        timeout_s: Timeout in seconds
        max_attempts: Maximum generation attempts
        enable_semantic_validation: Enable domain-specific validation
        enable_scratchpad: Enable reasoning scratchpad
        images: Optional images for multimodal generation
        audio: Optional audio for multimodal generation

    Returns:
        Validated Pydantic model instance
    """

    generator = get_enhanced_generator()

    # Auto-select strategy based on context
    if strategy == "auto":
        # Use grammar by default if available
        if _get_env_bool("KAGAMI_STRUCTURED_USE_GRAMMAR", True):
            strategy = GenerationStrategy.GRAMMAR_CONSTRAINED
        # Use function calling for OpenAI models
        elif model_name and "gpt" in model_name.lower() and os.getenv("OPENAI_API_KEY"):
            strategy = GenerationStrategy.FUNCTION_CALLING
        # Use scratchpad for complex schemas
        elif len(pydantic_model.model_fields) > 10:
            strategy = GenerationStrategy.SCRATCHPAD_REASONING
        else:
            strategy = GenerationStrategy.PROMPT_ONLY
    elif isinstance(strategy, str):
        strategy = GenerationStrategy(strategy)

    # Prepend synchronized rules prelude when available to harden prompts
    try:
        from kagami.core.rules_loader import build_prompt_prelude as _build_prelude

        prelude = _build_prelude(app_name="StructuredGeneration") or ""
    except Exception:
        prelude = ""

    sys_prompt = f"{prelude}\n\n{system_prompt}" if prelude else system_prompt

    result = await generator.generate_with_strategy(
        model_name=model_name,
        pydantic_model=pydantic_model,
        system_prompt=sys_prompt,
        user_prompt=user_prompt,
        strategy=strategy,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout_s=timeout_s,
        max_attempts=max_attempts,
        enable_semantic_validation=enable_semantic_validation,
        enable_scratchpad=enable_scratchpad or strategy == GenerationStrategy.SCRATCHPAD_REASONING,
        images=images,
        audio=audio,
    )

    return result


def _get_env_bool(name: str, default: bool = False) -> bool:
    """Get boolean environment variable."""
    v = (os.getenv(name) or ("1" if default else "0")).strip().lower()
    return v in ("1", "true", "yes", "on")


__all__ = [
    # Public API
    "EnhancedStructuredGenerator",
    "GenerationResult",
    "GenerationStrategy",
    "JSONRepairModule",
    "SemanticValidator",
    "UserFeedback",
    "generate_structured_enhanced",
    "get_enhanced_generator",
    "select_model_for",
]


def _env_tier(name: str, default: str) -> str:
    """Resolve tier env var to one of: fast|medium; otherwise default."""
    v = (os.getenv(name) or default).strip().lower()
    return v if v in ("fast", "medium") else default


def _is_api_allowed() -> bool:
    """Determine if external API usage is allowed for structured outputs.

    Conditions (all must be true):
    - OPENAI_API_KEY present
    - KAGAMI_ALLOW_API not explicitly false
    - KAGAMI_NETWORK_ALLOWED not explicitly false
    """
    has_key = bool(os.getenv("OPENAI_API_KEY"))
    allow_api = (os.getenv("KAGAMI_ALLOW_API") or "1").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    net_allowed = (os.getenv("KAGAMI_NETWORK_ALLOWED") or "1").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    return bool(has_key and allow_api and net_allowed)


def select_model_for(structured_use: str) -> str:
    """Select model by use-case with env-driven tier registry.

    Environment overrides (optional):
    - KAGAMI_STRUCTURED_MODEL_<USE> (explicit model override)
    - KAGAMI_STRUCTURED_TIER_DEFAULT=fast|medium (default tier)
    - KAGAMI_STRUCTURED_TIER_<APP>=fast|medium (per-app tier; e.g., PLANS)
    - KAGAMI_OPENAI_MODEL_FAST / KAGAMI_OPENAI_MODEL_MEDIUM (API defaults)
    - KAGAMI_TRANSFORMERS_MODEL_FAST / _MEDIUM (local defaults)
    """
    # Explicit per-use override (e.g., KAGAMI_STRUCTURED_MODEL_PLANS_SUGGEST)
    use_key = structured_use.replace(".", "_").upper()
    explicit = os.getenv(f"KAGAMI_STRUCTURED_MODEL_{use_key}")
    if explicit:
        return explicit.strip()

    # Resolve tier
    default_tier = _env_tier("KAGAMI_STRUCTURED_TIER_DEFAULT", "fast")
    app_key = structured_use.split(".")[0].upper()
    tier = _env_tier(f"KAGAMI_STRUCTURED_TIER_{app_key}", default_tier)

    # Prefer OpenAI if allowed
    if _is_api_allowed():
        if tier == "medium":
            return os.getenv("KAGAMI_OPENAI_MODEL_MEDIUM", "gpt-4-turbo-preview")
        return os.getenv("KAGAMI_OPENAI_MODEL_FAST", "gpt-3.5-turbo")

    # Fallback to local models (Transformers)
    if tier == "medium":
        return os.getenv("KAGAMI_TRANSFORMERS_MODEL_MEDIUM", "Qwen/Qwen2.5-7B-Instruct")  # Cached
    return os.getenv("KAGAMI_TRANSFORMERS_MODEL_FAST", "Qwen/Qwen3-1.7B")  # Cached
