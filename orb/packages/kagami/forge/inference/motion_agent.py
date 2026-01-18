"""Motion Agent integration for character animation.

This module integrates the Motion-Agent repository for generating
human motions through conversational interactions.
"""

import asyncio
import logging
import sys
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Resolve Motion-Agent repository path (support both external/ and root clones)
_CANDIDATE_PATHS = [
    Path("external/motion_agent_repo"),
    Path("motion_agent_repo"),
]
MOTION_AGENT_PATH: Path | None = None
for _p in _CANDIDATE_PATHS:
    if _p.exists() and any(_p.iterdir()):
        MOTION_AGENT_PATH = _p
        break
if MOTION_AGENT_PATH is not None:
    sys.path.insert(0, str(MOTION_AGENT_PATH))
    logger.info(f"Added Motion-Agent repo to sys.path: {MOTION_AGENT_PATH}")


class MotionAgent:
    """Wrapper for Motion-Agent conversational motion generation."""

    # Class-level semaphore for global concurrency control
    _gen_semaphore: asyncio.Semaphore | None = None

    def __init__(self) -> None:
        """Initialize Motion Agent."""
        self.initialized = False
        self.model = None

        if MOTION_AGENT_PATH is None or not MOTION_AGENT_PATH.exists():
            raise RuntimeError(
                "Motion-Agent repository not found. Run 'make forge-motion' "
                "to clone/setup Motion-Agent (or 'make forge-setup' for all Forge deps)."
            )

        self.motion_generator = None

    async def initialize(self) -> None:
        """Load Motion-Agent models and initialize generator."""
        if self.initialized:
            return
        try:
            import contextlib
            import os
            import subprocess

            # Ensure required checkpoints exist; attempt auto-download if missing
            repo = MOTION_AGENT_PATH
            assert repo is not None
            ckpt_dir = repo / "ckpt"
            vq_ckpt = ckpt_dir / "vqvae.pth"
            mm_ckpt = ckpt_dir / "motionllm.pth"
            mean_npy = (
                repo
                / "checkpoints"
                / "t2m"
                / "VQVAEV3_CB1024_CMT_H1024_NRES3"
                / "meta"
                / "mean.npy"
            )
            std_npy = (
                repo / "checkpoints" / "t2m" / "VQVAEV3_CB1024_CMT_H1024_NRES3" / "meta" / "std.npy"
            )

            if not (
                ckpt_dir.exists()
                and vq_ckpt.exists()
                and mm_ckpt.exists()
                and mean_npy.exists()
                and std_npy.exists()
            ):
                try:
                    logger.info(
                        "Missing Motion-Agent checkpoints. Attempting auto-install gdown and download..."
                    )
                    # Ensure gdown is installed for the prepare script
                    try:
                        __import__("gdown")
                    except Exception:
                        subprocess.run(
                            [sys.executable, "-m", "pip", "install", "-q", "gdown"], check=False
                        )
                    subprocess.run(
                        ["bash", str(repo / "prepare" / "download_ckpt.sh")],
                        cwd=str(repo),
                        check=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                    )
                    logger.info("Motion-Agent checkpoints downloaded successfully")
                except Exception as _dl_err:
                    raise RuntimeError(
                        f"Motion-Agent checkpoints not found and auto-download failed: {_dl_err}"
                    ) from None

            # Helper to temporarily set[Any] CWD into repo for relative paths
            @contextlib.contextmanager  # type: ignore[arg-type]
            def _in_repo() -> None:  # type: ignore[misc]
                prev = os.getcwd()
                os.chdir(str(repo))
                try:
                    yield
                finally:
                    os.chdir(prev)

            # Build args for MotionLLM (defaults + device override)
            with _in_repo():
                try:
                    from options.option_llm import get_args_parser
                except Exception:
                    get_args_parser = None

                if get_args_parser is not None:
                    args = get_args_parser()
                else:
                    from types import SimpleNamespace

                    args = SimpleNamespace()

                # Ensure required fields
                try:
                    import torch as _torch

                    device_str = (
                        "mps"
                        if getattr(_torch.backends, "mps", None)
                        and _torch.backends.mps.is_available()
                        else "cpu"
                    )
                except Exception:
                    device_str = "cpu"
                args.device = device_str
                # Provide save_dir expected by upstream MotionAgent
                args.save_dir = str(repo / "outputs")
                # Allow configuring backbone via env to avoid huge downloads during bring-up
                llm_bb = os.environ.get("MOTION_AGENT_LLM_BACKBONE", "sshleifer/tiny-gpt2")
                args.llm_backbone = llm_bb

                # Instantiate MotionLLM directly and prepare simple generator
                import torch as _torch
                from models.mllm import MotionLLM
                from utils.motion_utils import recover_from_ric

                class _SimpleMotionGenerator:
                    def __init__(self, args: Any) -> None:
                        self.args = args
                        self.model = MotionLLM(self.args)
                        # Load LoRA + embeddings
                        self.model.load_model("ckpt/motionllm.pth")
                        self.model.eval()
                        self.model.to(self.args.device)

                    def generate(
                        self, prompt: str, duration: float = 5.0, style: str = "natural"
                    ) -> Any:
                        motion_tokens = self.model.generate(prompt)
                        motion = self.model.net.forward_decoder(motion_tokens)
                        motion = self.model.denormalize(motion.detach().cpu().numpy())
                        motion = recover_from_ric(
                            _torch.from_numpy(motion).float().to(self.args.device), 22
                        )
                        # Return numpy array (frames x joints x 3)
                        return motion.squeeze().detach().cpu().numpy()

                self.motion_generator = None
                # Create generator within repo context so relative assets resolve
                self.motion_generator = _SimpleMotionGenerator(args)  # type: ignore[assignment]
                self.initialized = True
                logger.info("Motion-Agent successfully initialized (direct MotionLLM path)")
        except Exception as e:
            raise RuntimeError(
                f"Failed to initialize Motion-Agent: {e}. Ensure dependencies and checkpoints are installed."
            ) from None

    async def generate_motion(
        self, prompt: str, duration: float | None = None, style: str | None = None
    ) -> dict[str, Any] | None:
        """Generate motion based on text prompt.

        Args:
            prompt: Natural language description of the motion
            duration: Optional duration in seconds
            style: Optional style modifier (e.g., "energetic", "casual")

        Returns:
            Motion data or None if generation fails
        """
        if not self.initialized:
            await self.initialize()

        try:
            from kagami_observability.metrics import (
                MOTION_GENERATION_LATENCY_MS,
                MOTION_GENERATIONS,
            )

            # Generate motion using Motion-Agent
            logger.info(f"Generating motion for: {prompt}")

            # Prepare request parameters
            params = {
                "prompt": prompt,
                "duration": duration or 5.0,  # Default 5 seconds
                "style": style or "natural",
            }

            # Call Motion-Agent model
            gen = self.motion_generator.generate(**params)  # type: ignore  # Union member
            # Apply timeout budget for motion generation
            from kagami.core.config import get_int_config

            timeout_s = float(get_int_config("FORGE_MOTION_MAX_LATENCY_MS", 5000)) / 1000.0
            start_ms = time.time() * 1000.0
            # Concurrency gate
            max_conc = max(1, int(get_int_config("FORGE_MOTION_MAX_CONCURRENCY", 2)))
            if MotionAgent._gen_semaphore is None or MotionAgent._gen_semaphore._value != max_conc:
                MotionAgent._gen_semaphore = asyncio.Semaphore(max_conc)
            assert MotionAgent._gen_semaphore is not None
            async with MotionAgent._gen_semaphore:
                if hasattr(gen, "__await__"):
                    result = await asyncio.wait_for(gen, timeout=timeout_s)
                else:
                    # Offload blocking generation to thread pool
                    result = await asyncio.wait_for(
                        asyncio.to_thread(lambda: gen), timeout=timeout_s
                    )

            # Process and return the results
            # Normalize result into ndarray[Any, Any] and metadata
            motion = getattr(result, "motion_data", None)
            if motion is None and hasattr(result, "to_numpy"):
                motion = result.to_numpy()
            out = {
                "motion_data": motion,
                "duration": getattr(result, "duration", None),
                "fps": getattr(result, "fps", None),
                "style": getattr(result, "style", None),
                "metadata": getattr(result, "metadata", {}),
            }
            # Metrics
            try:
                MOTION_GENERATIONS.inc()
                MOTION_GENERATION_LATENCY_MS.observe(max(0.0, (time.time() * 1000.0) - start_ms))
            except Exception:
                pass
            return out
        except Exception as e:
            logger.error(f"Motion generation failed: {e}")
            raise
