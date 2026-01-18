"""Real Emu3.5 inference wrapper - no fallbacks.

Direct integration with Emu3.5 model for production use.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any, cast

import torch
from PIL import Image
from transformers.generation.utils import GenerationMixin

logger = logging.getLogger(__name__)


class Emu3InferenceEngine:
    """Real Emu3.5 inference engine."""

    def __init__(
        self,
        repo_path: Path,
        model_cache: Path,
        model_snapshot_path: Path | None = None,
        vq_snapshot_path: Path | None = None,
    ) -> None:
        self.repo_path = repo_path
        self.model_cache = model_cache
        self.model_snapshot_path = model_snapshot_path
        self.vq_snapshot_path = vq_snapshot_path

        # Model components (lazy-loaded)
        self.model: Any = None
        self.tokenizer: Any = None
        self.vq_model: Any = None
        self.cfg: Any = None
        self.special_token_ids: dict[str, int] = {}
        self._initialized = False

    async def initialize(self) -> None:
        """Load Emu3.5 models - PRODUCTION READY."""
        if self._initialized:
            return

        if not self.repo_path.exists():
            raise RuntimeError(
                f"Emu3.5 repo not found at {self.repo_path}\n"
                "Setup: make forge-emu (or set[Any] EMU_REPO_PATH to an existing checkout)"
            )

        # Add Emu3.5 to path
        sys.path.insert(0, str(self.repo_path))

        # Transformers compatibility shim (newer versions removed helper)
        try:
            from transformers.utils import import_utils as hf_import_utils
        except Exception as exc:  # pragma: no cover - defensive
            raise RuntimeError(f"Transformers import failed: {exc}") from exc

        if not hasattr(hf_import_utils, "is_torch_fx_available"):
            logger.info("Patching transformers.utils.import_utils.is_torch_fx_available -> False")

            def _is_torch_fx_available() -> bool:
                return False

            hf_import_utils.is_torch_fx_available = _is_torch_fx_available

        from transformers import modeling_utils as hf_modeling_utils

        if not getattr(hf_modeling_utils, "_kagami_tied_weights_patch", False):

            def _compat_get_tied_weight_keys(module: Any) -> list[str]:
                tied_weight_keys: list[str] = []
                for name, submodule in module.named_modules():
                    tied = getattr(submodule, "_tied_weights_keys", {}) or {}
                    if isinstance(tied, dict):
                        keys: Any = tied.keys()
                    elif isinstance(tied, (list, tuple, set)):
                        keys = tied
                    else:
                        keys = getattr(tied, "keys", lambda: [])()
                    tied_weight_keys.extend(f"{name}.{k}" if name else k for k in keys)
                return tied_weight_keys

            hf_modeling_utils._kagami_tied_weights_patch = True  # type: ignore[attr-defined]
            hf_modeling_utils._get_tied_weight_keys = _compat_get_tied_weight_keys  # type: ignore[assignment]

        # Ensure Emu3 inherits GenerationMixin for HF>=4.50 where PreTrainedModel removed it
        try:
            from src.emu3p5 import Emu3ForCausalLM

            if GenerationMixin not in Emu3ForCausalLM.__mro__:
                logger.info("Extending Emu3ForCausalLM with GenerationMixin (compat shim)")
                Emu3ForCausalLM.__bases__ = (*Emu3ForCausalLM.__bases__, GenerationMixin)
        except Exception as exc:
            logger.warning("Failed to extend Emu3ForCausalLM with GenerationMixin: %s", exc)

        # Import Emu3.5 modules
        from src.utils.model_utils import build_emu3p5

        # Build config - prefer explicit snapshot paths when provided
        model_path = str(self.model_snapshot_path) if self.model_snapshot_path else "BAAI/Emu3.5"
        vq_path = (
            str(self.vq_snapshot_path) if self.vq_snapshot_path else "BAAI/Emu3.5-VisionTokenizer"
        )
        tokenizer_path = str(self.repo_path / "src" / "tokenizer_emu3_ibq")

        # Determine device (optimized for MPS)
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            # MPS (Apple Silicon) - preferred for M3 Ultra
            hf_device = "mps"
            vq_device = "mps"
            logger.info("Using MPS (Apple Silicon) for Emu3.5")

            # MPS optimizations
            from kagami.core.utils.device import apply_mps_patches

            apply_mps_patches(force_env=True)

        elif torch.cuda.is_available():
            # CUDA (NVIDIA)
            hf_device = "cuda:0"
            vq_device = "cuda:0"
            logger.info("Using CUDA for Emu3.5")
        else:
            raise RuntimeError(
                "Emu3.5 requires GPU (CUDA or MPS). "
                "For CPU inference, use WORLD_PROVIDER=hunyuan or IMAGE_GEN_PROVIDER=openai"
            )

        logger.info(f"Loading Emu3.5 models to {hf_device}...")

        # Load models in executor to avoid blocking
        import asyncio

        loop = asyncio.get_running_loop()

        # MPS doesn't support Flash Attention - use eager attention
        kwargs = {}
        if hf_device == "mps":
            kwargs["attn_implementation"] = "eager"  # Disable Flash Attention for MPS
            logger.info("Using eager attention (Flash Attention not supported on MPS)")

        self.model, self.tokenizer, self.vq_model = await loop.run_in_executor(
            None,
            lambda: build_emu3p5(
                model_path,
                tokenizer_path,
                vq_path,
                vq_type="ibq",
                model_device=hf_device,
                vq_device=vq_device,
                **kwargs,
            ),
        )

        # Build special tokens map
        special_tokens = {
            "BOS": "<|extra_203|>",
            "EOS": "<|extra_204|>",
            "PAD": "<|endoftext|>",
            "BOI": "<|image start|>",
            "EOI": "<|image end|>",
            "BSS": "<|extra_100|>",
        }

        assert self.tokenizer is not None, "Tokenizer not initialized"
        self.special_token_ids = {k: self.tokenizer.encode(v)[0] for k, v in special_tokens.items()}

        # Emit metric
        try:
            pass

            # This will be measured by caller
        except Exception:
            pass

        self._initialized = True
        logger.info(f"✅ Emu3.5 models loaded successfully on {hf_device}")

    def build_prompt(
        self,
        prompt: str,
        mode: str,
        reference_image: Image.Image | None = None,
    ) -> tuple[str, str]:
        """Build Emu3.5 prompt with task-specific template.

        Returns:
            (full_prompt, unconditional_prompt)
        """
        # Task-specific templates
        task_map = {
            "world_exploration": "explore",
            "visual_narrative": "story",
            "x2i": "x2i",
            "t2i": "t2i",
        }
        task = task_map.get(mode, "story")

        # Build system prompt
        if reference_image is not None:
            unc_prompt = (
                "<|extra_203|>You are a helpful assistant. USER: <|IMAGE|> ASSISTANT: <|extra_100|>"
            )
            template = f"<|extra_203|>You are a helpful assistant for {task} task. USER: {{question}}<|IMAGE|> ASSISTANT: <|extra_100|>"
        else:
            unc_prompt = "<|extra_203|>You are a helpful assistant. USER:  ASSISTANT: <|extra_100|>"
            template = f"<|extra_203|>You are a helpful assistant for {task} task. USER: {{question}} ASSISTANT: <|extra_100|>"

        full_prompt = template.format(question=prompt)

        return full_prompt, unc_prompt

    async def generate(
        self,
        prompt: str,
        mode: str = "world_exploration",
        reference_image: Image.Image | None = None,
        num_steps: int = 5,
        guidance_scale: float = 3.0,
        max_tokens: int = 32768,
    ) -> list[dict[str, Any]]:
        """Generate interleaved vision-language output.

        Returns:
            List of output items, each with:
            - type: "text" or "image"
            - content: str (text) or PIL.Image (image)
        """
        if not self._initialized:
            await self.initialize()

        from src.utils.generation_utils import generate as emu_generate
        from src.utils.generation_utils import multimodal_decode
        from src.utils.input_utils import build_image

        # Build prompts
        full_prompt, unc_prompt = self.build_prompt(prompt, mode, reference_image)

        # Handle reference image
        if reference_image is not None:
            # Mock config for build_image
            class MockCfg:
                image_area = 518400  # Default from Emu config
                special_token_ids = self.special_token_ids

            image_str = build_image(reference_image, MockCfg(), self.tokenizer, self.vq_model)
            full_prompt = full_prompt.replace("<|IMAGE|>", image_str)
            unc_prompt = unc_prompt.replace("<|IMAGE|>", image_str)

        # Tokenize
        assert self.tokenizer is not None, "Tokenizer not initialized"
        assert self.model is not None, "Model not initialized"
        input_ids = self.tokenizer.encode(
            full_prompt, return_tensors="pt", add_special_tokens=False
        ).to(self.model.device)

        # Add BOS if needed
        if input_ids[0, 0] != self.special_token_ids["BOS"]:
            BOS = torch.tensor(
                [[self.special_token_ids["BOS"]]], device=input_ids.device, dtype=input_ids.dtype
            )
            input_ids = torch.cat([BOS, input_ids], dim=1)

        unconditional_ids = self.tokenizer.encode(
            unc_prompt, return_tensors="pt", add_special_tokens=False
        ).to(self.model.device)

        # Generation config (production-ready)
        class GenCfg:
            special_token_ids: dict[str, int]
            sampling_params: dict[str, Any]
            classifier_free_guidance: float
            unconditional_type: str
            streaming: bool

        cfg = GenCfg()
        cfg.special_token_ids = self.special_token_ids
        cfg.sampling_params = {
            "use_cache": True,
            "text_top_k": 1024,
            "text_top_p": 0.9,
            "text_temperature": 1.0,
            "image_top_k": 10240,
            "image_top_p": 1.0,
            "image_temperature": 1.0,
            "top_k": 131072,
            "top_p": 1.0,
            "temperature": 1.0,
            "max_new_tokens": max_tokens,
            "guidance_scale": guidance_scale,
            "use_differential_sampling": True,
            "do_sample": True,
            "num_beams": 1,
        }
        cfg.classifier_free_guidance = guidance_scale
        cfg.unconditional_type = "no_text"
        cfg.streaming = False

        # Run generation in executor (GPU-bound, blocking)
        import asyncio

        loop = asyncio.get_running_loop()

        def _run_generation() -> Any:
            """Run Emu3.5 generation (blocking GPU work)."""
            assert self.tokenizer is not None, "Tokenizer not initialized"
            assert self.vq_model is not None, "VQ model not initialized"
            results = []
            for result_tokens in emu_generate(
                cfg, self.model, self.tokenizer, input_ids, unconditional_ids, None
            ):
                try:
                    result_str = self.tokenizer.decode(result_tokens, skip_special_tokens=False)
                    mm_out = multimodal_decode(result_str, self.tokenizer, self.vq_model)

                    # Parse multimodal output
                    for item_type, content in mm_out:
                        if item_type == "text":
                            results.append({"type": "text", "content": content})
                        elif item_type == "image":
                            results.append({"type": "image", "content": content})

                except Exception as e:
                    logger.error(f"Generation error: {e}")
                    break
            return results

        # Execute in thread pool to avoid blocking event loop
        gen_results: Any = await loop.run_in_executor(None, _run_generation)

        if not gen_results:
            raise RuntimeError("Emu3.5 generation failed - no output produced") from None

        return cast(list[dict[str, Any]], gen_results)
