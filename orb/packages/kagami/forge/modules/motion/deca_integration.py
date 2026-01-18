#!/usr/bin/env python3
"""
FORGE - DECA Integration Module

HARDENED (Dec 22, 2025): DECA is REQUIRED when enabled. No soft fallbacks.

DECA (Detailed Expression Capture and Animation) is a research system for
reconstructing 3D facial geometry and expression parameters from images.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import torch

logger = logging.getLogger("ForgeMatrix.DECAIntegration")


@dataclass
class DECAConfig:
    """Configuration for DECA integration."""

    enabled: bool = True


class DECAIntegration:
    """DECA integration for face reconstruction + wrinkle maps.

    HARDENED: When enabled, DECA must be available.
    """

    def __init__(
        self, device: torch.device | None = None, config: DECAConfig | None = None
    ) -> None:
        self.device = device or torch.device("mps" if torch.backends.mps.is_available() else "cpu")
        self.config = config or DECAConfig()
        self.initialized = False
        self.available = False

        # Opaque handles to external DECA objects (if installed)
        self._deca: Any = None

    async def initialize(self) -> None:
        """Initialize DECA.

        HARDENED: Raises if enabled but DECA unavailable.
        """
        if not self.config.enabled:
            self.initialized = True
            self.available = False
            return

        # HARDENED: Require DECA when enabled
        try:
            from decalib.deca import DECA
            from decalib.utils.config import cfg as deca_cfg

            self._deca = DECA(config=deca_cfg, device=str(self.device))
            self.available = True
            logger.info("✅ DECA initialized for face reconstruction")
        except ImportError as e:
            raise RuntimeError(
                "DECA is enabled but decalib is not installed. "
                "Install with: pip install git+https://github.com/yfeng95/DECA"
            ) from e
        except Exception as e:
            raise RuntimeError(f"DECA initialization failed: {e}") from e

        self.initialized = True

    async def reconstruct_face(self, image: torch.Tensor) -> dict[str, Any]:
        """Reconstruct a face model from an input image.

        HARDENED: Requires DECA to be available.

        Args:
            image: Input image tensor [B, C, H, W]

        Returns:
            Dict containing face_model, expression params, etc.
        """
        if not self.available:
            raise RuntimeError("DECA not available - call initialize() first")
        if self._deca is None:
            raise RuntimeError("DECA not initialized")

        # Run DECA reconstruction
        with torch.no_grad():
            codedict = self._deca.encode(image)
            opdict = self._deca.decode(codedict)

        return {
            "face_model": opdict.get("trans_verts"),
            "shape": codedict.get("shape"),
            "expression": codedict.get("exp"),
            "pose": codedict.get("pose"),
            "detail": codedict.get("detail"),
        }

    async def generate_wrinkle_maps(self, codedict: dict[str, Any]) -> dict[str, Any]:
        """Generate wrinkle maps from DECA code dictionary.

        HARDENED: Requires DECA to be available.
        """
        if not self.available:
            raise RuntimeError("DECA not available - call initialize() first")
        if self._deca is None:
            raise RuntimeError("DECA not initialized")

        with torch.no_grad():
            opdict = self._deca.decode(codedict, render_orig=True)

        return {
            "uv_texture_gt": opdict.get("uv_texture_gt"),
            "displacement_map": opdict.get("displacement_map"),
        }
