"""MPS/CoreML acceleration for homr OMR engine.

Patches ONNX Runtime session creation to use CoreMLExecutionProvider
on Apple Silicon instead of falling back to CPU.

homr uses ONNX Runtime for inference with hardcoded CUDAExecutionProvider.
On Apple Silicon Macs, this falls back to CPU. This module patches homr
to use CoreMLExecutionProvider for GPU acceleration via Metal.

Performance:
    - CoreML: ~2-3x faster than CPU on M3 Ultra
    - Unified memory: No CPU↔GPU transfer overhead

Usage:
    from kagami_virtuoso.score_parser.mps_patch import patch_homr_for_mps
    patch_homr_for_mps()  # Call once before using homr

References:
    - https://onnxruntime.ai/docs/execution-providers/CoreML-ExecutionProvider.html
    - homr source: encoder_inference.py, decoder_inference.py, inference_segnet.py
"""

from __future__ import annotations

import logging
import platform
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Track if patches have been applied
_patches_applied = False


def get_optimal_providers() -> list[str]:
    """Get optimal ONNX execution providers for current platform.

    Priority order:
        1. CoreMLExecutionProvider (Apple Silicon)
        2. CUDAExecutionProvider (NVIDIA GPU)
        3. CPUExecutionProvider (fallback)

    Returns:
        List of provider names in priority order.
    """
    import onnxruntime as ort

    available = ort.get_available_providers()
    providers = []

    # Apple Silicon: prefer CoreML
    if platform.system() == "Darwin" and platform.machine() == "arm64":
        if "CoreMLExecutionProvider" in available:
            providers.append("CoreMLExecutionProvider")
            logger.debug("CoreMLExecutionProvider available for Apple Silicon")

    # NVIDIA GPU
    if "CUDAExecutionProvider" in available:
        providers.append("CUDAExecutionProvider")
        logger.debug("CUDAExecutionProvider available")

    # Always include CPU as fallback
    if "CPUExecutionProvider" in available:
        providers.append("CPUExecutionProvider")

    if not providers:
        providers = ["CPUExecutionProvider"]

    return providers


def is_apple_silicon() -> bool:
    """Check if running on Apple Silicon."""
    return platform.system() == "Darwin" and platform.machine() == "arm64"


def patch_homr_for_mps() -> bool:
    """Patch homr to use CoreML/MPS on Apple Silicon.

    Modifies homr's ONNX session creation to include CoreMLExecutionProvider
    in the providers list. Safe to call multiple times.

    Returns:
        True if patches were applied, False if already patched or not needed.
    """
    global _patches_applied

    if _patches_applied:
        logger.debug("homr MPS patches already applied")
        return False

    # Get optimal providers for this platform
    providers = get_optimal_providers()
    provider_str = " → ".join(providers)
    logger.info(f"Patching homr ONNX sessions: {provider_str}")

    try:
        import onnxruntime as ort

        patch_results = []

        # Patch encoder inference
        enc_result = _patch_encoder_inference(providers)
        patch_results.append(("Encoder", enc_result))

        # Patch decoder inference
        dec_result = _patch_decoder_inference(providers)
        patch_results.append(("Decoder", dec_result))

        # Patch segmentation inference
        seg_result = _patch_segnet_inference(providers)
        patch_results.append(("Segnet", seg_result))

        # Check if at least some patches succeeded
        successful = [name for name, result in patch_results if result]
        if successful:
            _patches_applied = True
            logger.info(f"✓ homr MPS/CoreML patches applied: {', '.join(successful)}")
            return True
        else:
            logger.warning("No homr patches could be applied")
            return False

    except ImportError as e:
        logger.warning(f"Could not patch homr (not installed?): {e}")
        return False
    except Exception as e:
        logger.error(f"Error patching homr: {e}")
        return False


def _patch_encoder_inference(providers: list[str]) -> bool:
    """Patch homr.transformer.encoder_inference.Encoder.

    Returns:
        True if patch was successful.
    """
    try:
        import homr.transformer.encoder_inference as enc
        import onnxruntime as ort

        _original_init = enc.Encoder.__init__

        def patched_init(self, path: str, use_gpu: bool) -> None:
            """Patched __init__ with optimal providers."""
            # Use our provider list regardless of use_gpu flag
            # (CoreML IS GPU acceleration on Apple Silicon)
            try:
                self.encoder = ort.InferenceSession(path, providers=providers)
                logger.debug(f"Encoder using: {self.encoder.get_providers()}")
            except Exception as e:
                logger.warning(f"Failed with {providers}, falling back: {e}")
                self.encoder = ort.InferenceSession(path)

            self.input_name = self.encoder.get_inputs()[0].name
            self.output_name = self.encoder.get_outputs()[0].name

        enc.Encoder.__init__ = patched_init
        logger.debug("Patched Encoder.__init__")
        return True

    except Exception as e:
        logger.warning(f"Could not patch encoder_inference: {e}")
        return False


def _patch_decoder_inference(providers: list[str]) -> bool:
    """Patch homr.transformer.decoder_inference.get_decoder.

    Returns:
        True if patch was successful.
    """
    try:
        import homr.transformer.decoder_inference as dec
        import onnxruntime as ort

        _original_get = dec.get_decoder

        def patched_get_decoder(
            config: dec.Config,
            path: str,
            use_gpu: bool,
        ) -> dec.ScoreDecoder:
            """Patched get_decoder with optimal providers."""
            try:
                onnx_transformer = ort.InferenceSession(path, providers=providers)
                logger.debug(f"ScoreDecoder using: {onnx_transformer.get_providers()}")
            except Exception as e:
                logger.warning(f"Failed with {providers}, falling back: {e}")
                onnx_transformer = ort.InferenceSession(path)

            return dec.ScoreDecoder(onnx_transformer, config=config)

        dec.get_decoder = patched_get_decoder
        logger.debug("Patched decoder_inference.get_decoder")
        return True

    except Exception as e:
        logger.warning(f"Could not patch decoder_inference: {e}")
        return False


def _patch_segnet_inference(providers: list[str]) -> bool:
    """Patch homr.segmentation.inference_segnet.Segnet.

    Returns:
        True if patch was successful.
    """
    try:
        import homr.segmentation.inference_segnet as seg
        import onnxruntime as ort

        _original_init = seg.Segnet.__init__

        def patched_init(self, model_path: str, use_gpu: bool) -> None:
            """Patched __init__ with optimal providers."""
            try:
                self.model = ort.InferenceSession(model_path, providers=providers)
                logger.debug(f"Segnet using: {self.model.get_providers()}")
            except Exception as e:
                logger.warning(f"Failed with {providers}, falling back: {e}")
                self.model = ort.InferenceSession(model_path)

            self.input_name = self.model.get_inputs()[0].name
            self.output_name = self.model.get_outputs()[0].name

        seg.Segnet.__init__ = patched_init
        logger.debug("Patched Segnet.__init__")
        return True

    except Exception as e:
        logger.warning(f"Could not patch inference_segnet: {e}")
        return False


def get_patch_status() -> dict[str, bool | str]:
    """Get status of MPS patches.

    Returns:
        Dict with patch status information.
    """
    import onnxruntime as ort

    return {
        "patches_applied": _patches_applied,
        "platform": f"{platform.system()} {platform.machine()}",
        "is_apple_silicon": is_apple_silicon(),
        "available_providers": ort.get_available_providers(),
        "optimal_providers": get_optimal_providers(),
    }


__all__ = [
    "get_optimal_providers",
    "get_patch_status",
    "is_apple_silicon",
    "patch_homr_for_mps",
]
