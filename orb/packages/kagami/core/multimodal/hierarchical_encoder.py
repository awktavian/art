"""Hierarchical multimodal encoder with multi-scale representations.

Encodes observations at three levels of abstraction:
- Low: Spatial features (edges, textures)
- Mid: Semantic features (objects, parts)
- High: Abstract features (scenes, concepts)

Enables faster reasoning by selecting appropriate abstraction level.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class HierarchicalEncoder:
    """Multi-scale hierarchical encoder for visual observations.

    Architecture:
    - Level 1 (Low): 32 channels, 64x64 resolution - Spatial details
    - Level 2 (Mid): 64 channels, 32x32 resolution - Object semantics
    - Level 3 (High): 128 channels, 16x16 resolution - Scene concepts

    Benefits:
    - Fast reasoning at appropriate level
    - Better disentanglement
    - Compositional understanding
    """

    def __init__(self, input_channels: int = 3) -> None:
        """Initialize hierarchical encoder.

        Args:
            input_channels: Number of input channels (3 for RGB)
        """
        self.input_channels = input_channels
        self._model = None
        self._device = "cpu"

        try:
            import torch
            import torch.nn as nn

            class HierarchicalNet(nn.Module):
                def __init__(self, in_channels: Any) -> None:
                    super().__init__()

                    # Level 1: Spatial features (low-level)
                    self.low_conv = nn.Sequential(
                        nn.Conv2d(in_channels, 32, 7, 1, 3),
                        nn.BatchNorm2d(32),
                        nn.ReLU(),
                        nn.Conv2d(32, 32, 3, 1, 1),
                        nn.BatchNorm2d(32),
                        nn.ReLU(),
                    )

                    # Level 2: Object features (mid-level)
                    self.mid_conv = nn.Sequential(
                        nn.Conv2d(32, 64, 3, 2, 1),  # Downsample
                        nn.BatchNorm2d(64),
                        nn.ReLU(),
                        nn.Conv2d(64, 64, 3, 1, 1),
                        nn.BatchNorm2d(64),
                        nn.ReLU(),
                    )

                    # Level 3: Scene features (high-level)
                    self.high_conv = nn.Sequential(
                        nn.Conv2d(64, 128, 3, 2, 1),  # Downsample
                        nn.BatchNorm2d(128),
                        nn.ReLU(),
                        nn.Conv2d(128, 128, 3, 1, 1),
                        nn.BatchNorm2d(128),
                        nn.ReLU(),
                    )

                    # Projections to embedding space
                    self.low_proj = nn.Linear(32 * 64 * 64, 128)
                    self.mid_proj = nn.Linear(64 * 32 * 32, 256)
                    self.high_proj = nn.Linear(128 * 16 * 16, 512)

                def forward(self, x: Any) -> dict[str, Any]:
                    # x: [B, 3, 64, 64]

                    # Level 1: Spatial
                    low = self.low_conv(x)  # [B, 32, 64, 64]
                    low_flat = low.flatten(1)
                    low_emb = self.low_proj(low_flat)  # [B, 128]

                    # Level 2: Semantic
                    mid = self.mid_conv(low)  # [B, 64, 32, 32]
                    mid_flat = mid.flatten(1)
                    mid_emb = self.mid_proj(mid_flat)  # [B, 256]

                    # Level 3: Abstract
                    high = self.high_conv(mid)  # [B, 128, 16, 16]
                    high_flat = high.flatten(1)
                    high_emb = self.high_proj(high_flat)  # [B, 512]

                    return {
                        "low": low_emb,  # Detailed spatial
                        "mid": mid_emb,  # Semantic objects
                        "high": high_emb,  # Abstract concepts
                        "features": {
                            "low_spatial": low,
                            "mid_semantic": mid,
                            "high_abstract": high,
                        },
                    }

            self._device = (
                "cuda"
                if torch.cuda.is_available()
                else (
                    "mps"
                    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
                    else "cpu"
                )
            )

            self._model = HierarchicalNet(input_channels).to(self._device)

            logger.info(
                f"✓ HierarchicalEncoder initialized: "
                f"3 levels (32/64/128 channels), device={self._device}"
            )

        except ImportError:
            logger.debug("PyTorch not available for hierarchical encoding")

    def encode(self, observation: Any) -> dict[str, Any]:
        """Encode observation at all hierarchy levels.

        Args:
            observation: RGB image [B, 3, H, W] or [3, H, W]

        Returns:
            Dict with low/mid/high embeddings and raw features
        """
        if self._model is None:
            raise RuntimeError(
                "HierarchicalEncoder is not initialized (PyTorch missing or encoder init failed)."
            )

        try:
            import torch
            import torch.nn.functional as F

            # Convert to tensor
            if not isinstance(observation, torch.Tensor):
                observation = torch.tensor(observation, dtype=torch.float32)

            # Ensure on correct device
            observation = observation.to(self._device)

            # Add batch dimension if needed
            if len(observation.shape) == 3:
                observation = observation.unsqueeze(0)

            # Resize to 64x64 if needed
            if observation.shape[-2:] != (64, 64):
                observation = F.interpolate(
                    observation, size=(64, 64), mode="bilinear", align_corners=False
                )

            # Forward pass
            with torch.no_grad():
                result = self._model(observation)

            # Convert to lists for serialization
            return {
                "low": result["low"][0].cpu().tolist(),
                "mid": result["mid"][0].cpu().tolist(),
                "high": result["high"][0].cpu().tolist(),
                "features": {
                    k: v[0].cpu().numpy() if hasattr(v[0], "cpu") else v[0]
                    for k, v in result["features"].items()
                },
            }

        except Exception as e:
            logger.error(f"Hierarchical encoding failed: {e}")
            return {"low": [0.0] * 128, "mid": [0.0] * 256, "high": [0.0] * 512}

    def encode_at_level(self, observation: Any, level: str = "high") -> Any:
        """Encode at specific abstraction level.

        Args:
            observation: Image input
            level: "low", "mid", or "high"

        Returns:
            Embedding at requested level
        """
        result = self.encode(observation)
        return result.get(level, result["high"])


# Singleton
_HIERARCHICAL_ENCODER: HierarchicalEncoder | None = None


def get_hierarchical_encoder(input_channels: int = 3) -> HierarchicalEncoder:
    """Get or create hierarchical encoder.

    Args:
        input_channels: Number of input channels

    Returns:
        HierarchicalEncoder instance
    """
    global _HIERARCHICAL_ENCODER
    if _HIERARCHICAL_ENCODER is None:
        _HIERARCHICAL_ENCODER = HierarchicalEncoder(input_channels=input_channels)
    return _HIERARCHICAL_ENCODER
