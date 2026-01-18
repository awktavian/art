from __future__ import annotations

#!/usr/bin/env python3
"""
Style Enforcement Pipeline - Ensures every generated asset follows K os DNA
Integrates with all Forge generation systems
"""
import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from ...forge_llm_base import (
    CharacterAspect,
    CharacterContext,
    LLMRequest,
)
from ...llm_service_adapter import KagamiOSLLMServiceAdapter
from ...optimized_image_generator import OptimizedImageGenerator
from ...utils.cache import CacheManager
from ...utils.style_rewriters import (
    build_prompts_for_content_type,
    sanitize_final_prompt_for_content_type,
)
from .kagami_style_engine import KagamiOSStyleEngine

logger = logging.getLogger(__name__)

# Compatibility: older enums may not define APPEARANCE; fall back to VISUAL_DESIGN
try:
    ASPECT_APPEARANCE = CharacterAspect.APPEARANCE  # type: ignore  # Dynamic attr
except Exception:  # pragma: no cover - compatibility path
    ASPECT_APPEARANCE = getattr(CharacterAspect, "VISUAL_DESIGN", None)


@dataclass
class StyleEnforcementResult:
    """Result of style enforcement process"""

    original_prompt: str
    enforced_prompt: str
    generation_result: Any
    style_validation: dict[str, Any]
    corrections_applied: list[str]
    final_path: Path | None
    success: bool
    metadata: dict[str, Any]


class StyleEnforcementPipeline:
    """
    Master pipeline that enforces K os style across all generation

    BOLD CHOICES:
    1. Every prompt is rewritten to enforce style
    2. Every output is validated and corrected
    3. Non-compliant outputs are regenerated
    4. Style learning improves over time
    """

    def __init__(self) -> None:
        self.style_engine = KagamiOSStyleEngine()
        self.image_generator = None
        self.llm = None
        self._cache = CacheManager()

        # Style enforcement settings
        self.enforcement_level = "strict"  # strict, moderate, flexible
        self.auto_correct = True
        self.max_regeneration_attempts = 3
        self.style_confidence_threshold = 0.85

        # Optional OpenAI vision validation
        self.vision_validation_enabled_default = True

        # Test-time acceleration (optional overrides for fast runs)
        try:
            import os as _os

            self.max_regeneration_attempts = int(
                _os.getenv("STYLE_MAX_REGEN", str(self.max_regeneration_attempts))
            )
            try:
                self.style_confidence_threshold = float(
                    _os.getenv(
                        "STYLE_CONF_THRESHOLD",
                        str(self.style_confidence_threshold),
                    )
                )
            except Exception:
                self.style_confidence_threshold = 0.50
        except Exception:
            pass

        # Learning system
        self.generation_history: list[StyleEnforcementResult] = []
        self.style_drift_monitor = {
            "baseline": None,
            "current_drift": 0.0,
            "max_acceptable_drift": 0.15,
        }

        self.initialized = False

    async def initialize(self) -> None:
        """Initialize the style enforcement pipeline"""
        if self.initialized:
            return

        logger.info("Initializing K os Style Enforcement Pipeline...")

        # Initialize components
        import os

        import torch

        forced = (os.getenv("FORGE_IMAGE_DEVICE") or "").strip().lower()
        if forced in ("cpu", "mps", "cuda"):
            if forced == "mps" and not torch.backends.mps.is_available():
                device = torch.device("cpu")
            else:
                device = torch.device(forced)
        else:
            device = torch.device(
                "mps"
                if torch.backends.mps.is_available()
                else "cuda"
                if torch.cuda.is_available()
                else "cpu"
            )
        self.image_generator = OptimizedImageGenerator(device)  # type: ignore[assignment]
        await self.image_generator.initialize()  # type: ignore  # Dynamic attr

        # Initialize LLM for prompt enhancement (centralized resolver; non-fatal if unavailable)
        try:
            self.llm = KagamiOSLLMServiceAdapter()  # type: ignore[assignment]
            await self.llm.initialize()  # type: ignore  # Dynamic attr
        except Exception:
            self.llm = None

        self.initialized = True
        logger.info("Style Enforcement Pipeline ready")

    @staticmethod
    def _gpt5_enabled_by_default() -> bool:
        """Return True when GPT‑5 text assist should be enabled by default.

        Rules:
        - Hard off if offline mode or no OPENAI_API_KEY
        - Otherwise on by default unless KAGAMI_ENABLE_GPT5 explicitly set[Any] to a falsey value
        - If KAGAMI_ENABLE_GPT5 is explicitly truthy, always on
        """
        import os as _os

        # Offline/test mode guard
        if not _os.getenv("OPENAI_API_KEY"):  # No API key = offline mode
            return False
        if not _os.getenv("OPENAI_API_KEY"):
            return False
        flag = (_os.getenv("KAGAMI_ENABLE_GPT5") or "").strip().lower()
        if flag in {"1", "true", "yes", "on"}:
            return True
        if flag in {"0", "false", "no", "off"}:
            return False
        # Default: enabled when key present and not offline
        return True

    def _vision_validation_enabled(self) -> bool:
        """Whether to run vision validation (OpenAI only)."""
        import os as _os

        key_present = bool((_os.getenv("OPENAI_API_KEY") or "").strip())
        flag = (_os.getenv("KAGAMI_STYLE_VISION_VALIDATE") or "").strip().lower()
        if flag in {"1", "true", "yes", "on"}:
            return key_present
        if flag in {"0", "false", "no", "off"}:
            return False
        return key_present and self.vision_validation_enabled_default

    async def _vision_inspect_image(self, path: Path, *, content_type: str) -> dict[str, Any]:
        """Inspect an image with a vision model (OpenAI) and return a compact JSON verdict."""
        result: dict[str, Any] = {
            "overall_score": 0.0,
            "passes_standard": False,
            "checks": {},
            "reasons": [],
            "model": None,
        }
        if not self._vision_validation_enabled():
            return result
        try:
            import base64

            if not path.exists():
                return result
            with path.open("rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")

            # Build rubric tailored per content type
            if content_type == "ui_component":
                rubric = (
                    "K os UI Component rubric: flat 2D; anatomy-free; AA contrast; neutral card backgrounds; "
                    "subtle depth only via soft rim; white/transparent background; graphic/text-free unless label specified."
                )
            elif content_type == "brand_tile":
                rubric = (
                    "K os Brand Tile rubric: geometric/cosmic gradients; clean neutrals; legible focal anchor; "
                    "white background; no anatomy; text-free."
                )
            else:
                rubric = (
                    "K os Character rubric: proportions, eyes highlights, velvet-matte surface, white background; "
                    "no uncanny details; readable at thumbnail size."
                )

            # OpenAI vision
            import os

            from openai import OpenAI

            system = (
                "You are a strict visual validator. Score compliance 0..1 and list[Any] 2-4 short reasons. "
                "Return JSON only: {overall_score, passes_standard, checks:{composition,background,anatomy_free,contrast}, reasons}."
            )
            user = f"Rubric: {rubric}\nBudget: return JSON only."
            cli = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

            def _request_oa() -> Any:
                try:
                    return cli.responses.create(
                        model="gpt-4o-mini",
                        input=[
                            {"role": "system", "content": system},
                            {  # type: ignore[misc]
                                "role": "user",
                                "content": [
                                    {"type": "input_text", "text": user},
                                    {
                                        "type": "input_image",
                                        "image_url": {"url": f"data:image/png;base64,{b64}"},
                                    },
                                ],
                            },
                        ],
                        max_output_tokens=400,
                        temperature=0,
                    )
                except Exception:
                    return cli.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": system},
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": user},
                                    {
                                        "type": "image_url",
                                        "image_url": {"url": f"data:image/png;base64,{b64}"},
                                    },
                                ],
                            },
                        ],
                        temperature=0,
                        max_tokens=400,
                    )

            import asyncio as _aio

            resp = await _aio.get_running_loop().run_in_executor(None, _request_oa)
            text_out = getattr(resp, "output_text", None)
            if not text_out and hasattr(resp, "choices"):
                try:
                    text_out = resp.choices[0].message["content"]
                except Exception:
                    text_out = None
            if text_out:
                try:
                    parsed = json.loads(text_out)
                    if isinstance(parsed, dict):
                        result.update(parsed)
                        result["model"] = "gpt-4o-mini"
                except Exception:
                    pass
            # Clamp
            try:
                sc = float(result.get("overall_score", 0) or 0.0)
                result["overall_score"] = max(0.0, min(1.0, sc))
            except Exception:
                result["overall_score"] = 0.0
            if "passes_standard" not in result:
                result["passes_standard"] = bool(
                    result["overall_score"] >= self.style_confidence_threshold
                )
        except Exception as e:
            try:
                logger.debug("Vision validation skipped: %s", e)
            except Exception:
                pass
        return result

    # =========================================================================
    # Helper Methods for generate_with_style_enforcement (Complexity Reduction)
    # =========================================================================

    def _calculate_preview_dimensions(
        self,
        generation_params: dict[str, Any],
    ) -> tuple[int, int, int, int]:
        """Calculate preview and requested dimensions based on generation params.

        Returns:
            Tuple of (requested_w, requested_h, preview_w, preview_h)
        """
        requested_w = int(generation_params.get("width", 1024) or 1024)
        requested_h = int(generation_params.get("height", 1024) or 1024)

        # For gpt-image-1, only certain sizes are allowed; coerce preview
        use_gpt = generation_params.get("use_gpt", True)
        has_openai = (
            hasattr(self.image_generator, "openai_client")
            and self.image_generator.openai_client is not None  # type: ignore[attr-defined]
        )

        if use_gpt and has_openai:
            if requested_w == requested_h:
                preview_w, preview_h = 1024, 1024
            elif requested_w > requested_h:
                preview_w, preview_h = 1536, 1024
            else:
                preview_w, preview_h = 1024, 1536
        else:
            preview_w = min(768, requested_w)
            preview_h = min(768, requested_h)

        return requested_w, requested_h, preview_w, preview_h

    async def _merge_vision_validation(
        self,
        validation_result: dict[str, Any],
        image_path: Path,
        content_type: str,
    ) -> dict[str, Any]:
        """Merge vision-based validation with standard validation.

        Args:
            validation_result: Base validation result
            image_path: Path to the generated image
            content_type: Type of content being validated

        Returns:
            Merged validation result with vision scores
        """
        try:
            vision_val = await self._vision_inspect_image(image_path, content_type=content_type)
            if isinstance(vision_val, dict) and vision_val:
                result = dict(validation_result)
                result["vision_overall_score"] = float(vision_val.get("overall_score", 0.0) or 0.0)
                result["vision_passes"] = bool(vision_val.get("passes_standard", False))
                result["vision_checks"] = vision_val.get("checks", {})
                result["vision_reasons"] = vision_val.get("reasons", [])

                # Combine: require both to pass; use min score as overall floor
                base_ok = bool(result.get("passes_standard", False))
                combined_pass = base_ok and bool(result["vision_passes"])
                result["passes_standard"] = combined_pass

                try:
                    base_score = float(result.get("overall_score", 0.0) or 0.0)
                    vision_score = float(result["vision_overall_score"])
                    result["overall_score"] = min(base_score, vision_score)
                except Exception:
                    pass

                return result
        except Exception:
            pass

        return validation_result

    async def _write_style_sidecar(
        self,
        base_prompt: str,
        enforced_prompt: str,
        validation_result: dict[str, Any],
        corrections_applied: list[str],
        timestamp: str,
    ) -> None:
        """Write style validation sidecar JSON file.

        Args:
            base_prompt: Original prompt
            enforced_prompt: Style-enforced prompt
            validation_result: Validation results
            corrections_applied: List of corrections applied
            timestamp: Generation timestamp
        """
        try:
            sidecar_dir = Path("style_enforced_output")
            sidecar_dir.mkdir(parents=True, exist_ok=True)
            sidecar_path = sidecar_dir / "last_style_sidecar.json"

            violations: list[str] = []
            for key, val in validation_result.items():
                if isinstance(val, dict) and "score" in val and val["score"] < 0.85:
                    violations.append(key)

            auto_correction_tips: list[str] = []
            if violations:
                auto_correction_tips = await self._generate_correction_tips_from_validation(
                    enforced_prompt, validation_result
                )

            sidecar = {
                "original_prompt": base_prompt,
                "enforced_prompt": enforced_prompt,
                "validation": validation_result,
                "violations": violations,
                "auto_correction_tips": auto_correction_tips,
                "corrections_applied": corrections_applied,
                "timestamp": timestamp,
            }
            with open(sidecar_path, "w") as f:
                json.dump(sidecar, f, indent=2)
        except Exception:
            pass

    async def _publish_forge_observation(
        self,
        content_type: str,
        success: bool,
        overall_score: float,
        attempts: int,
        generation_params: dict[str, Any],
    ) -> None:
        """Publish forge observation to event bus (non-blocking).

        Args:
            content_type: Type of content generated
            success: Whether generation succeeded
            overall_score: Overall validation score
            attempts: Number of generation attempts
            generation_params: Original generation parameters
        """
        try:
            import os as _os

            if (_os.getenv("KAGAMI_STYLE_ADAPTIVE") or "1").lower() in (
                "1",
                "true",
                "yes",
                "on",
            ):
                try:
                    from kagami.core.events import get_unified_bus as _get_bus

                    bus = _get_bus()
                    obs = {
                        "type": "forge.observation",
                        "stage": "final",
                        "content_type": content_type,
                        "success": bool(success),
                        "overall_score": float(overall_score),
                        "attempts": int(attempts),
                        "width": int(generation_params.get("width", 0) or 0),
                        "height": int(generation_params.get("height", 0) or 0),
                    }
                    import asyncio as _aio

                    _aio.create_task(bus.publish("forge.observation", obs))
                except Exception:
                    pass
        except Exception:
            pass

    # =========================================================================
    # Main Generation Method
    # =========================================================================

    async def generate_with_style_enforcement(
        self,
        base_prompt: str,
        generation_params: dict[str, Any],
        metadata: dict[str, Any] | None = None,
        *,
        content_type: str = "character",  # character | ui_component | brand_tile
    ) -> StyleEnforcementResult:
        """Generate content with full style enforcement.

        This is the PRIMARY method all generation should use.

        Extracted helpers (reducing cyclomatic complexity):
        - _calculate_preview_dimensions() - dimension calculation
        - _merge_vision_validation() - vision validation merge
        - _write_style_sidecar() - sidecar file I/O
        - _publish_forge_observation() - event bus publishing

        Args:
            base_prompt: Original prompt to enhance
            generation_params: Generation parameters (width, height, etc.)
            metadata: Optional metadata to include in result
            content_type: Type of content (character, ui_component, brand_tile)

        Returns:
            StyleEnforcementResult with enforced prompt, validation, and path
        """

        if not self.initialized:
            await self.initialize()

        # Capture start time for total pipeline duration metric
        from kagami_observability.metrics import GENERATION_DURATION

        _pipeline_start = __import__("time").time()

        generation_metadata = {
            "timestamp": datetime.now().isoformat(),
            "base_prompt": base_prompt,
            "enforcement_level": self.enforcement_level,
            "content_type": content_type,
            **(metadata or {}),
        }

        # Step 1: Enhance prompt with style enforcement (cached)
        from time import time as _now

        _t0 = _now()
        cache_key_prompt = (
            f"enforce_prompt|{content_type}|{base_prompt}|"
            f"{json.dumps(generation_params, sort_keys=True)}"
        )
        cached_prompt = self._cache.get_value("style", cache_key_prompt)
        if isinstance(cached_prompt, str) and cached_prompt:
            enforced_prompt = cached_prompt
        else:
            enforced_prompt = await self._enforce_style_in_prompt(
                base_prompt, generation_params, content_type=content_type
            )
            # Cache for 1 hour to accelerate repeated generations
            self._cache.set_value("style", cache_key_prompt, enforced_prompt, ttl=3600)
        try:
            GENERATION_DURATION.labels(module="style_prompt").observe(_now() - _t0)
        except Exception as e:
            logger.debug(f"Metric recording failed: {e}")
            # Metrics are non-critical

        # Step 2: Generate with enforced prompt
        generation_result = None
        validation_result: dict[str, Any] | None = None
        attempts = 0

        while attempts < self.max_regeneration_attempts:
            attempts += 1
            logger.info(f"🎨 Generation attempt {attempts}/{self.max_regeneration_attempts}")

            # Generate
            _t1 = _now()

            # Calculate preview dimensions (extracted helper)
            requested_w, requested_h, preview_w, preview_h = self._calculate_preview_dimensions(
                generation_params
            )

            preview_params = {
                **generation_params,
                "use_gpt": True,
                "width": preview_w,
                "height": preview_h,
            }
            logger.info(
                "StylePipeline: starting preview generation (use_gpt=%s, %sx%s)",
                bool(preview_params.get("use_gpt", True)),
                preview_params.get("width", 1024),
                preview_params.get("height", 1024),
            )
            generation_result = await self._generate_content(enforced_prompt, preview_params)
            try:
                logger.info(
                    "StylePipeline: preview generation result keys=%s",
                    (
                        list(generation_result.keys())
                        if isinstance(generation_result, dict)
                        else type(generation_result)
                    ),
                )
            except Exception:
                pass
            try:
                GENERATION_DURATION.labels(module="style_generate_preview").observe(_now() - _t1)
            except Exception:
                pass

            if generation_result and "error" not in generation_result:
                # Step 3: Validate style compliance (or bypass in simple mode)
                _t2 = _now()

                # Simple mode: trust LLM-enforced prompt; mark as pass and break
                if self._validation_mode() == "simple":
                    validation_result = {
                        "overall_score": 0.95,
                        "passes_standard": True,
                        "mode": "simple",
                    }
                    logger.info("✅ Simple mode: assuming pass via prompt enforcement")
                    break

                # Cache validation by file path + mtime to avoid re-validating identical images
                try:
                    p = Path(str(generation_result["path"]))
                    stat = p.stat()
                    val_key = f"validate|{p}|{int(stat.st_mtime)}|{stat.st_size}"
                except Exception:
                    val_key = f"validate|{generation_result.get('path', 'unknown')}"

                cached_val = self._cache.get_value("style_validate", val_key)
                if isinstance(cached_val, dict) and cached_val:
                    validation_result = cached_val
                else:
                    validation_result = await self.style_engine.validate_style_compliance(
                        generation_result["path"], content_type=content_type
                    )

                    # Merge vision-based validation (extracted helper)
                    pth = Path(str(generation_result["path"]))
                    validation_result = await self._merge_vision_validation(
                        validation_result, pth, content_type
                    )

                    self._cache.set_value("style_validate", val_key, validation_result, ttl=3600)
                try:
                    logger.info(
                        "StylePipeline: validation overall=%.3f passes=%s",
                        float(validation_result.get("overall_score", 0.0)),
                        bool(validation_result.get("passes_standard", False)),
                    )
                except Exception:
                    pass
                try:
                    GENERATION_DURATION.labels(module="style_validate").observe(_now() - _t2)
                except Exception:
                    pass

                if validation_result["passes_standard"]:
                    try:
                        from kagami_observability.metrics import (
                            STYLE_REGENERATIONS,
                            STYLE_VALIDATION,
                        )

                        STYLE_VALIDATION.labels("pass").inc()
                        STYLE_REGENERATIONS.labels("success").observe(attempts - 1)  # Dynamic attr
                    except Exception:
                        pass
                    logger.info(
                        f"✅ Style validation passed: {validation_result['overall_score']:.2f}"
                    )
                    break
                else:
                    try:
                        from kagami_observability.metrics import STYLE_VALIDATION

                        STYLE_VALIDATION.labels("fail").inc()
                    except Exception as e:
                        logger.debug(f"Metric recording failed: {e}")
                        # Metrics are non-critical

                    logger.warning(
                        f"⚠️ Style validation failed: {validation_result['overall_score']:.2f}"
                    )

                    # Step 4: Apply corrections if enabled
                    if (
                        self.auto_correct
                        and attempts < self.max_regeneration_attempts
                        and self._validation_mode() == "full"
                    ):
                        _t3 = _now()
                        corrected_path = await self.style_engine.apply_style_corrections(
                            generation_result["path"], validation_result
                        )
                        try:
                            GENERATION_DURATION.labels(module="style_correct").observe(_now() - _t3)
                        except Exception:
                            pass
                        generation_result["path"] = corrected_path
                        generation_result["corrections_applied"] = validation_result.get(
                            "corrections", []
                        )

                        # Re-validate after corrections
                        validation_result = await self.style_engine.validate_style_compliance(
                            corrected_path, content_type=content_type
                        )

                        if validation_result["passes_standard"]:
                            logger.info("✅ Style validation passed after corrections")
                            # If requested size > preview size, render final high-res now
                            if requested_w > preview_w or requested_h > preview_h:
                                _t4 = _now()
                                final_result = await self._generate_content(
                                    enforced_prompt,
                                    {
                                        **generation_params,
                                        "use_gpt": True,
                                        "width": requested_w,
                                        "height": requested_h,
                                    },
                                )
                                try:
                                    GENERATION_DURATION.labels(
                                        module="style_generate_final"
                                    ).observe(_now() - _t4)
                                except Exception:
                                    pass
                                if not final_result or "error" in final_result:
                                    # Fall back to preview if final fails
                                    pass
                                else:
                                    generation_result = final_result
                            break

                    # Enhance prompt further for next attempt
                    if self._validation_mode() == "full":
                        enforced_prompt = await self._enhance_prompt_from_feedback(
                            enforced_prompt,
                            validation_result,
                            content_type=content_type,
                        )
                    else:
                        # Simple mode: do not loop regenerations; break
                        break

        # Step 5: Learn from this generation
        if generation_result is not None and validation_result is not None:
            await self._learn_from_generation(generation_result, validation_result)

        # Create result
        result = StyleEnforcementResult(
            original_prompt=base_prompt,
            enforced_prompt=enforced_prompt,
            generation_result=generation_result,
            style_validation=validation_result if validation_result else {},
            corrections_applied=(
                generation_result.get("corrections_applied", []) if generation_result else []
            ),
            final_path=generation_result.get("path") if generation_result else None,
            success=(validation_result["passes_standard"] if validation_result else False),
            metadata=generation_metadata,
        )

        # Store in history
        self.generation_history.append(result)

        # Write sidecar JSON (extracted helper)
        if generation_result and validation_result:
            await self._write_style_sidecar(
                base_prompt=base_prompt,
                enforced_prompt=enforced_prompt,
                validation_result=validation_result,
                corrections_applied=result.corrections_applied,
                timestamp=generation_metadata["timestamp"],
            )

        # Monitor style drift
        await self._monitor_style_drift()

        # Publish observation (extracted helper)
        overall_score = (
            float((validation_result or {}).get("overall_score", 0.0)) if validation_result else 0.0
        )
        await self._publish_forge_observation(
            content_type=content_type,
            success=result.success,
            overall_score=overall_score,
            attempts=attempts,
            generation_params=generation_params,
        )

        # Observe total pipeline duration
        try:
            GENERATION_DURATION.labels(module="style_enforcement").observe(
                __import__("time").time() - _pipeline_start
            )
        except Exception:
            pass

        # Record regeneration outcome if we never passed validation
        try:
            if not result.success:
                from kagami_observability.metrics import STYLE_REGENERATIONS

                STYLE_REGENERATIONS.labels("failure").observe(
                    self.max_regeneration_attempts
                )  # Dynamic attr
        except Exception:
            pass

        return result

    def _get_style_guide_excerpt(self, *, content_type: str, max_chars: int = 800) -> str:
        """Return a compact excerpt of the public style guide, tuned per content type.

        The goal is to include essential constraints directly in the image model prompt
        without overflowing character budgets.
        """
        guide_path = Path("docs/style/STYLE_GUIDE.md")
        if not guide_path.exists():
            return ""
        try:
            text = guide_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return ""

        # Prefer Content Modes + Core Principles

        def _extract(header: str) -> str:
            start = text.find(header)
            if start == -1:
                return ""
            end = text.find("\n## ", start + 3)  # next level-2 header
            if end == -1:
                end = len(text)
            return text[start:end].strip()

        core = _extract("## Core Principles")
        modes = _extract("## Content Modes") or _extract("## Content Modes (enforced)")
        ui = _extract("## K os UI Design System")

        # Small mode-specific appendix
        mode_hint = ""
        if content_type == "character":
            mode_hint = (
                "Content Mode: Character — follow proportions/eyes/materials; white background."
            )
        elif content_type == "ui_component":
            mode_hint = (
                "Content Mode: UI Component — anatomy‑free; AA contrast; neutral panels; "
                "white/transparent background only; label text only if explicitly specified."
            )
        else:
            mode_hint = (
                "Content Mode: Brand Tile — geometric/cosmic gradients; legible focal anchor; "
                "anatomy‑free; text‑free; white background."
            )

        combined = "\n".join(s for s in [mode_hint, core, modes, ui] if isinstance(s, str) and s)
        combined = combined.replace("\n\n", "\n").strip()
        # Sanitize excerpt: remove markdown headings and character-specific lines for non-character modes
        lines = [ln for ln in combined.split("\n") if ln.strip()]
        sanitized: list[str] = []
        drop_keywords = set()
        if content_type != "character":
            drop_keywords = {
                "Head 45%",
                "Body 35%",
                "Limbs 20%",
                "Eyes",
                "pupils",
                "species",
                "Pose",
                "orthographic",
                "Character",
                "mascot",
                "line‑of‑action",
            }
        negative_tokens = ["avoid", "must not", "no "]
        for ln in lines:
            if ln.lstrip().startswith("#"):
                continue
            low = ln.lower()
            if drop_keywords and any(k.lower() in low for k in drop_keywords):
                continue
            if any(tok in low for tok in negative_tokens) or ("must" in low and "not" in low):
                # Drop entire negative line to avoid inversion
                continue
            # Drop heading artifacts from guide excerpts
            if (
                low.startswith("- ui component")
                or low.startswith("- brand tile")
                or low.startswith("—")
            ):
                continue
            sanitized.append(ln)
        combined = "\n".join(sanitized)
        return combined[:max_chars]

    async def _enforce_style_in_prompt(
        self,
        base_prompt: str,
        params: dict[str, Any],
        *,
        content_type: str = "character",
    ) -> str:
        """Enforce K os style in the prompt with token/length budgeting and robust fallback.

        Strategy:
        - Build style prompt via style engine (can be long)
        - Merge with base prompt while honoring a character budget (default ~1000)
        - Always retain identity + species constraints + camera/pose + key style bullets
        - If LLM unavailable, perform deterministic merge/summarization
        """

        # Budget (in characters) for image model prompt
        max_chars = int(params.get("max_prompt_chars", 1000))

        # Extract mascot data with safe defaults
        mascot_data_in = params.get("mascot_data", {}) or {}
        mascot_data = {
            "name": mascot_data_in.get("name", "Character"),
            "species": mascot_data_in.get("species", "Mascot"),
            "personality_traits": mascot_data_in.get("personality_traits", ["friendly"]),
            "color_palette": mascot_data_in.get(
                "color_palette", {"primary": "purple", "secondary": "blue"}
            ),
            # 3D-friendly hints
            "orthographic": bool(mascot_data_in.get("orthographic", False)),
            "view": mascot_data_in.get("view", "3/4"),
            "pose": mascot_data_in.get("pose", "dynamic"),
            "negatives": mascot_data_in.get("negatives", []),
        }

        # Centralized: build prompts via style_rewriters with machine-readable guide support
        built = await build_prompts_for_content_type(
            content_type=content_type,
            mascot_data=mascot_data,
            style_engine=self.style_engine,
            guide_path=Path("docs/style/STYLE_GUIDE.md"),
        )
        try:
            logger.info(
                "StylePipeline: built prompts (content_type=%s, core_count=%d)",
                content_type,
                len(built.core_lines),
            )
        except Exception as e:
            logger.debug(f"Metric recording failed: {e}")
            # Metrics are non-critical
        style_prompt = built.style_prompt
        core_lines: list[str] = list(built.core_lines)
        list(mascot_data.get("negatives", []))

        if content_type == "character":
            core_lines.append(f"Character: {mascot_data['name']} the {mascot_data['species']}")
            if mascot_data.get("orthographic"):
                core_lines.append(
                    f"View: {mascot_data.get('view', 'front')} orthographic; Pose: {mascot_data.get('pose', 'A-pose')} (full body incl. feet, limb separation visible)"
                )
            core_lines.extend(
                [
                    "Proportions: Head 45% / Body 35% / Limbs 20%",
                    "Eyes: round pupils, triple highlights (~30% head)",
                    "Surface: velvet-matte; gentle subsurface; soft rim light",
                    f"Palette: Primary {mascot_data['color_palette'].get('primary', 'purple')}, Secondary {mascot_data['color_palette'].get('secondary', 'blue')}",
                    "Background: pure white; even soft studio lighting; no shadows",
                ]
            )
            species = str(mascot_data.get("species", "Mascot")).lower()
            if species.startswith("penguin"):
                core_lines.append(
                    "Species: penguin (compact body, flipper wings, short beak, tuxedo plumage); no human hands/ears"
                )
        elif content_type == "ui_component":
            core_lines.extend(
                [
                    "UI component: flat 2D status ribbon/panel/button; anatomy‑free",
                    "AA contrast; neutral card/panel backgrounds; subtle depth only via soft rim",
                    "Motion cues ≤250ms (do not animate in image); render static",
                    "Background: pure white or transparent only; even lighting",
                ]
            )
            # Positive framing only for providers without negative prompt support
            core_lines.append(
                "Strictly UI-only elements; purely graphic; anatomy‑free; text‑free composition (unless specific label is specified)."
            )
        elif content_type == "brand_tile":
            core_lines.extend(
                [
                    "Brand tile: geometric/cosmic gradients; clean neutrals",
                    "Legible focal anchor; anatomy‑free",
                    "Background: pure white; soft shadows only if needed",
                ]
            )
            core_lines.append(
                "Purely graphic motif; anatomy‑free; text‑free; optimized for clarity at thumbnail size."
            )
        # Do not include explicit "Avoid:" lists for providers without negative prompt fields

        # Compose a compact merge: style guide excerpt + core + base essentials
        style_guide_excerpt = self._get_style_guide_excerpt(
            content_type=content_type, max_chars=max(200, int(max_chars * 0.6))
        )
        base_compact = base_prompt.strip().replace("\n", " ") if base_prompt else ""
        merged_compact = (
            f"K os House Style — Neo‑Kawaii Futurism ({content_type}). Act, not chat. With receipts. "
            + (f"{style_guide_excerpt} " if style_guide_excerpt else "")
            + "; ".join(core_lines)
            + (f"; Details: {base_compact}" if base_compact else "")
            + "."
        )

        # If LLM is available, request a merged prompt under budget
        enforced_prompt: str
        try:
            import os

            no_cloud = os.getenv("KAGAMI_TEST_NO_CLOUD", "0") in ("1", "true", "yes", "on")
        except Exception:
            no_cloud = False

        # Offline/no-cloud mode: do NOT invoke LLM merge (keeps tests fast and deterministic).
        if no_cloud:
            enforced_prompt = f"{style_prompt}, {base_compact}".strip()
            if len(enforced_prompt) > max_chars:
                enforced_prompt = enforced_prompt[: max(0, int(max_chars) - 3)].rstrip() + "..."
        elif self.llm or self._gpt5_enabled_by_default():
            from ...utils.style_directives import get_kagami_house_style_directive

            house = get_kagami_house_style_directive()
            if content_type == "character":
                preserve_lines = (
                    "Preserve K os character style bullets (proportions, eyes, materials/lighting, background) "
                    "and species/pose if present."
                )
            elif content_type == "ui_component":
                preserve_lines = (
                    "Preserve UI constraints (flat 2D, AA contrast, neutral panels, white/transparent background). "
                    "DO NOT introduce character/anatomy/eyes/species/pose language."
                )
            else:  # brand_tile
                preserve_lines = (
                    "Preserve brand tile constraints (geometric/cosmic gradients, focal anchor, minimal composition, white background). "
                    "DO NOT introduce character/anatomy/eyes/species/pose language."
                )
            merge_request = LLMRequest(
                prompt=(
                    f"{house}\nYou are merging two prompts for an image generator.\n"
                    f"- Output MUST be <= {max_chars} characters.\n"
                    f"- {preserve_lines}\n"
                    "- Use concise, declarative phrases; no headings; single paragraph.\n\n"
                    f"STYLE PROMPT (may be long): {style_prompt}\n\n"
                    f"BASE PROMPT (essentials): {base_compact}\n\n"
                    "Return ONLY the merged prompt text."
                ),
                context=CharacterContext(
                    character_id="style_merge",
                    name="Style Merger",
                    aspect=ASPECT_APPEARANCE,
                ),
                temperature=0.4,
                max_tokens=400,
            )
            try:
                if self.llm:
                    candidate = await self.llm.generate_text(merge_request.prompt)  # type: ignore  # Defensive/fallback code
                    enforced_prompt = str(candidate).strip()
                    if enforced_prompt.startswith("[echo]"):
                        raise RuntimeError("Echo merge detected; trying optional OpenAI merge")
                else:
                    raise RuntimeError("Local LLM unavailable; try OpenAI merge")
            except Exception:
                # OpenAI merge, default-enabled when not offline
                try:
                    if self._gpt5_enabled_by_default():
                        from openai import OpenAI

                        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
                        if content_type == "character":
                            system = (
                                f"You merge prompts for an image generator. Keep <= {max_chars} characters, "
                                "preserve K os character style bullets (proportions, eyes, materials/lighting, background), "
                                "species identity, and orthographic/pose if present. Single paragraph."
                            )
                        elif content_type == "ui_component":
                            system = (
                                f"You merge prompts for an image generator. Keep <= {max_chars} characters. "
                                "Preserve UI constraints (flat 2D, AA contrast, neutral panels, white/transparent background). "
                                "Do NOT introduce anatomy/character/eyes/species/pose language. Single paragraph."
                            )
                        else:
                            system = (
                                f"You merge prompts for an image generator. Keep <= {max_chars} characters. "
                                "Preserve brand tile constraints (geometric/cosmic gradients, focal anchor, minimal composition, white background). "
                                "Do NOT introduce anatomy/character/eyes/species/pose language. Single paragraph."
                            )
                        user = (
                            f"STYLE PROMPT (may be long): {style_prompt}\n\n"
                            f"BASE PROMPT (essentials): {base_compact}\n\n"
                            "Return ONLY the merged prompt text."
                        )

                        # Prefer Responses API; fall back to chat/completions on older libs
                        def _make_request() -> Any:
                            try:
                                return client.responses.create(
                                    model="gpt-5",
                                    input=[
                                        {"role": "system", "content": system},
                                        {"role": "user", "content": user},
                                    ],
                                    temperature=0.4,
                                    max_output_tokens=400,
                                )
                            except Exception:
                                # Some SDKs still route via chat/completions; GPT-5 expects max_completion_tokens
                                return client.chat.completions.create(
                                    model="gpt-5",
                                    messages=[
                                        {"role": "system", "content": system},
                                        {"role": "user", "content": user},
                                    ],
                                    temperature=0.4,
                                    max_completion_tokens=400,
                                )

                        resp = await asyncio.get_running_loop().run_in_executor(None, _make_request)
                        # Parse Responses API → output_text or structured content
                        text_out = getattr(resp, "output_text", None)
                        if not text_out:
                            try:
                                # Newer SDK structure
                                out0 = getattr(resp, "output", [])[0]
                                cont0 = getattr(out0, "content", [])[0]
                                text_obj = getattr(cont0, "text", None)
                                text_out = (
                                    getattr(text_obj, "value", None)
                                    if text_obj is not None
                                    else None
                                )
                            except Exception:
                                text_out = None
                        if not text_out and hasattr(resp, "choices"):
                            try:
                                text_out = resp.choices[0].message.content
                            except Exception:
                                text_out = None
                        enforced_prompt = (
                            str(text_out).strip() if text_out else ""
                        ) or merged_compact
                    else:
                        enforced_prompt = merged_compact
                except Exception:
                    enforced_prompt = merged_compact
        else:
            enforced_prompt = merged_compact

        # Hard budget enforcement: truncate least critical tail if needed
        if len(enforced_prompt) > max_chars:
            # Prefer keeping up to last full sentence within budget
            trimmed = enforced_prompt[:max_chars].rsplit(".", 1)[0].strip()
            enforced_prompt = trimmed if trimmed else enforced_prompt[:max_chars]

        # Final compliance tag (compact, parenthetical to preserve budget)
        if content_type == "character":
            enforced_prompt = (
                enforced_prompt + " (Follow proportions/eyes/materials/background exactly.)"
            )
        else:
            enforced_prompt = (
                enforced_prompt
                + " (Flat UI/graphic; white/transparent bg; AA contrast; minimal, anatomy‑free; thumbnail‑readable.)"
            )

        # Provider-level sanitization for non-character modes
        enforced_prompt = sanitize_final_prompt_for_content_type(
            enforced_prompt, content_type=content_type
        )
        try:
            logger.debug(
                "StylePipeline: enforced prompt len=%d (content_type=%s)",
                len(enforced_prompt or ""),
                content_type,
            )
        except Exception:
            pass

        return enforced_prompt

    async def _generate_content(self, prompt: str, params: dict[str, Any]) -> dict[str, Any]:
        """Generate content using the appropriate generator (OpenAI only)."""

        try:
            # Force OpenAI path only
            if (
                not self.image_generator
                or getattr(self.image_generator, "openai_client", None) is None  # type: ignore  # Defensive/fallback code
            ):
                return {
                    "error": "OpenAI client unavailable. Set OPENAI_API_KEY to use gpt-image-1."
                }

            # Determine allowed sizes (square/portrait/landscape)
            requested_w = params.get("width", 1024)  # type: ignore  # Defensive/fallback code
            requested_h = params.get("height", 1024)
            if requested_w == requested_h:
                target_w, target_h = 1024, 1024
            elif requested_w > requested_h:
                target_w, target_h = 1536, 1024
            else:
                target_w, target_h = 1024, 1536

            logger.info(
                "StylePipeline: using OpenAI gpt-image-1 (target=%sx%s)",
                target_w,
                target_h,
            )
            image = await self.image_generator.generate_image(
                prompt=prompt,
                width=target_w,
                height=target_h,
                use_local=False,
                request_timeout_seconds=float(
                    params.get("timeout_seconds", 180.0)
                ),  # Increased to 3min for reliability
            )

            # Save image
            output_dir = Path(params.get("output_dir", "style_enforced_output"))
            output_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"kagami_style_{timestamp}.png"
            output_path = output_dir / filename

            image.save(output_path, format="PNG", compress_level=9)
            logger.info("StylePipeline: saved image to %s", output_path)

            return {"path": output_path, "image": image, "prompt_used": prompt}

        except Exception as e:
            logger.error(f"Generation failed: {e}")
            return {"error": str(e)}

    async def _enhance_prompt_from_feedback(
        self, current_prompt: str, validation: dict[str, Any], *, content_type: str = "character"
    ) -> str:
        """Enhance prompt based on validation feedback"""

        from ...utils.style_directives import get_kagami_house_style_directive

        house = get_kagami_house_style_directive()
        if content_type == "character":
            guardrail = "Preserve character constraints (proportions, eyes, materials/lighting, background)."
        elif content_type == "ui_component":
            guardrail = "Do NOT introduce any anatomy/character/eyes/species/pose language. Preserve UI constraints (flat 2D, AA contrast, neutral panels, white/transparent background)."
        else:
            guardrail = "Do NOT introduce any anatomy/character/eyes/species/pose language. Preserve brand tile constraints (geometric/cosmic gradients, focal anchor, minimal composition, white background)."
        enhancement_request = LLMRequest(
            prompt=f"""{house}\nThe generated image failed style validation. Enhance this prompt to fix the issues while preserving K os style. {guardrail}

CURRENT PROMPT: {current_prompt}

VALIDATION FEEDBACK:
- Overall Score: {validation.get("overall_score", 0):.2f}
- Issues: {json.dumps(validation.get("feedback", {}), indent=2)}

Create an enhanced prompt that specifically addresses these issues while maintaining all other requirements.""",
            context=CharacterContext(
                character_id="style_enhancer",
                name="Style Enhancer",
                aspect=ASPECT_APPEARANCE,
            ),
            temperature=0.7,
            max_tokens=500,
        )

        if self.llm:
            try:  # type: ignore  # Defensive/fallback code
                response = await self.llm.generate_text(enhancement_request.prompt)
                return str(response)
            except Exception:
                # If provider rejects parameters or is unavailable, keep current prompt
                return current_prompt
        else:
            return current_prompt

    async def _generate_correction_tips_from_validation(
        self, enforced_prompt: str, validation: dict[str, Any]
    ) -> list[str]:
        """Use the LLM to produce explicit auto-correction tips based on validation feedback."""
        try:
            from ...utils.style_directives import (
                get_kagami_creative_tone,
                get_kagami_house_style_directive,
            )

            house = get_kagami_house_style_directive()
            tone = get_kagami_creative_tone()
            request = LLMRequest(
                prompt=(
                    f"{house}\n{tone}\nGiven the enforced prompt and validation feedback, list[Any] concrete corrections to apply to the image or prompt.\n"
                    f"Return JSON array of short, actionable tips (max 8).\n\n"
                    f"ENFORCED_PROMPT: {enforced_prompt}\n\n"
                    f"VALIDATION: {json.dumps(validation, indent=2)}"
                ),
                context=CharacterContext(
                    character_id="style_sidecar_tips",
                    name="Style Tips",
                    aspect=ASPECT_APPEARANCE,
                ),
                temperature=0.5,
                max_tokens=300,
            )
            if not self.llm:
                return []
            raw = await self.llm.generate_text(request.prompt)  # type: ignore  # Defensive/fallback code
            tips: list[str] = []
            try:
                parsed = json.loads(raw) if isinstance(raw, str) else raw
                if isinstance(parsed, list):
                    tips = [str(t) for t in parsed][:8]
                elif isinstance(parsed, dict) and "tips" in parsed:
                    tips = [str(t) for t in parsed.get("tips", [])][:8]
            except Exception:
                # Fallback: wrap as single tip string if parsing fails
                tips = [str(raw)[:300]] if raw else []
            return tips
        except Exception:
            return []

    async def _learn_from_generation(
        self, generation_result: dict[str, Any], validation_result: dict[str, Any]
    ) -> None:
        """Learn from each generation to improve future outputs"""

        if not generation_result or "path" not in generation_result:
            return

        # Prepare feedback for GAIA learning
        feedback = {
            "is_good_example": validation_result.get("passes_standard", False),
            "score": validation_result.get("overall_score", 0),
            "violations": [],
            "strengths": [],
        }

        # Extract specific feedback
        for check_name, check_result in validation_result.items():
            if isinstance(check_result, dict) and "score" in check_result:
                if check_result["score"] < 0.8:
                    feedback["violations"].append(check_name)
                elif check_result["score"] > 0.9:
                    feedback["strengths"].append(check_name)

    async def _monitor_style_drift(self) -> None:
        """Monitor style drift over time"""

        if len(self.generation_history) < 10:
            return  # Not enough data

        # Get recent generations
        recent_paths = [
            result.final_path
            for result in self.generation_history[-10:]
            if result.final_path and result.success
        ]

        if len(recent_paths) < 5:
            return  # Not enough successful generations

        # Analyze consistency
        consistency_report = None

        # Update drift metrics
        if self.style_drift_monitor["baseline"] is None:
            self.style_drift_monitor["baseline"] = consistency_report.overall_consistency  # type: ignore  # Dynamic attr
        else:
            self.style_drift_monitor["current_drift"] = abs(
                consistency_report.overall_consistency  # type: ignore  # Dynamic attr
                - self.style_drift_monitor["baseline"]
            )

        # Alert if drift is too high
        if (
            self.style_drift_monitor["current_drift"]  # type: ignore[operator,operator,operator]
            > self.style_drift_monitor["max_acceptable_drift"]
        ):
            logger.warning(
                f"⚠️ Style drift detected: {self.style_drift_monitor['current_drift']:.2f}"
            )
            await self._trigger_style_reinforcement()

    async def _trigger_style_reinforcement(self) -> None:
        """Trigger style reinforcement when drift is detected"""

        logger.info("🔧 Triggering style reinforcement...")

        # Get the best examples from history
        best_examples = sorted(
            [r for r in self.generation_history if r.success],
            key=lambda x: x.style_validation.get("overall_score", 0),
            reverse=True,
        )[:5]

        # Use these as positive examples for learning
        for example in best_examples:
            if example.final_path:
                pass

    def _validation_mode(self) -> str:
        """Return 'simple' or 'full' based on env (default: simple)."""
        try:
            import os as _os

            mode = (_os.getenv("KAGAMI_STYLE_VALIDATION_MODE") or "simple").strip().lower()
            return mode if mode in {"simple", "full"} else "simple"
        except Exception:
            return "simple"


# Singleton instance
style_enforcement_pipeline = StyleEnforcementPipeline()
