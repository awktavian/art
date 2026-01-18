from __future__ import annotations

"""Core ML runtime stubs for Apple Neural Engine (ANE) acceleration.

This module provides minimal wrappers to run select encoders via Core ML.
Currently implements a vision encoder wrapper. Feature-gated via env.
"""
import logging
from typing import Any

logger = logging.getLogger(__name__)


class CoreMLVisionEncoder:
    """Run a vision encoder via Core ML.

    Expects an .mlmodel path compiled as MLProgram. Input format: NHWC float32.
    Output: (B, D) embeddings as numpy array.
    """

    def __init__(self, model_path: str) -> None:
        try:
            import coremltools as ct

            self._ct = ct
        except Exception as e:
            raise RuntimeError(f"coremltools not available: {e}") from None

        try:
            # Lazy import to avoid hard dependency when unused
            import coremltools as ct

            self._mlmodel = ct.models.MLModel(model_path)
            logger.info("Loaded Core ML vision model")
        except Exception as e:
            raise RuntimeError(f"Failed to load Core ML model: {e}") from None

    def encode(self, images_nhwc: Any) -> Any:
        """Encode a batch of images (NHWC float32) using Core ML.

        Args:
            images_nhwc: numpy array (B, H, W, C), float32

        Returns:
            numpy array (B, D) embeddings
        """
        try:
            import numpy as np

            if images_nhwc is None:
                raise ValueError("images_nhwc is None")
            arr = np.asarray(images_nhwc, dtype=np.float32)
            if arr.ndim != 4 or arr.shape[-1] not in (1, 3):
                raise ValueError("Expected NHWC with C=1 or 3")

            # Core ML models often accept per-image dictionaries; batch by loop
            outputs = []
            # Best effort: infer input/output names
            in_names = (
                list(self._mlmodel.input_description._fd_spec)
                if hasattr(self._mlmodel, "input_description")
                else []
            )
            out_names = (
                list(self._mlmodel.output_description._fd_spec)
                if hasattr(self._mlmodel, "output_description")
                else []
            )
            input_key = in_names[0] if in_names else "image"
            output_key = out_names[0] if out_names else "embeddings"
            for i in range(arr.shape[0]):
                out = self._mlmodel.predict({input_key: arr[i]})
                vec = out.get(output_key)
                if vec is None:
                    # Attempt to take first value
                    try:
                        vec = next(iter(out.values()))
                    except Exception:
                        raise RuntimeError("Core ML vision output missing") from None
                outputs.append(vec)
            return np.asarray(outputs, dtype=np.float32)
        except Exception as e:
            raise RuntimeError(f"Core ML vision encode failed: {e}") from None


__all__ = ["CoreMLVisionEncoder"]
