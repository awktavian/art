"""Data Stream Controller — 5-mode data acquisition.

This is a small, test-oriented controller that cycles through acquisition modes.
It supports LeCun-style "Perception" integration without requiring any heavy
model dependencies.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import torch


class DataMode(Enum):
    """Acquisition modes."""

    PASSIVE_OBSERVATION = "passive_observation"
    ACTIVE_FOVEATION = "active_foveation"
    ACTIVE_EXPLORATION = "active_exploration"
    REPLAY = "replay"
    SLEEP = "sleep"


@dataclass
class DataStreamConfig:
    """Configuration for DataStreamController."""

    cycle_duration_steps: int = 100
    # Number of foveated crops per call
    foveation_samples: int = 3
    # Crop size for foveation (square)
    foveation_crop_size: int = 16


@dataclass
class DataSample:
    """A single acquired sample."""

    mode: DataMode
    observation: torch.Tensor
    timestamp: float = field(default_factory=lambda: time.time())
    metadata: dict[str, Any] = field(default_factory=dict[str, Any])


class DataStreamController:
    """Cycles through 5 modes and provides simple acquisition helpers."""

    MODES: tuple[DataMode, ...] = (
        DataMode.PASSIVE_OBSERVATION,
        DataMode.ACTIVE_FOVEATION,
        DataMode.ACTIVE_EXPLORATION,
        DataMode.REPLAY,
        DataMode.SLEEP,
    )

    def __init__(self, config: DataStreamConfig | None = None):
        self.config = config or DataStreamConfig()
        self._step_count = 0
        self._mode_samples: dict[DataMode, int] = dict[str, Any].fromkeys(self.MODES, 0)

    def step(self) -> None:
        """Advance one step (updates internal mode schedule)."""
        self._step_count += 1

    def get_current_mode(self) -> DataMode:
        """Return the current acquisition mode."""
        # Within one cycle_duration_steps window, we should traverse multiple modes.
        cycle = max(1, int(self.config.cycle_duration_steps))
        mode_period = max(1, cycle // len(self.MODES))
        idx = (self._step_count // mode_period) % len(self.MODES)
        return self.MODES[idx]

    def passive_observe(self, observation: torch.Tensor) -> DataSample:
        """Record an observation without modification."""
        mode = DataMode.PASSIVE_OBSERVATION
        self._mode_samples[mode] += 1
        return DataSample(mode=mode, observation=observation)

    def active_foveate(self, observation: torch.Tensor) -> list[DataSample]:
        """Return a few cropped 'foveated' views of an image-like tensor.

        Supports [C,H,W] or [H,W]. For non-image tensors, returns a single sample.
        """
        mode = DataMode.ACTIVE_FOVEATION
        samples: list[DataSample] = []

        if observation.dim() not in (2, 3):
            self._mode_samples[mode] += 1
            return [DataSample(mode=mode, observation=observation, metadata={"foveated": False})]

        if observation.dim() == 2:
            obs = observation.unsqueeze(0)  # [1,H,W]
        else:
            obs = observation  # [C,H,W]

        _, H, W = obs.shape
        crop = min(self.config.foveation_crop_size, H, W)
        if crop <= 0:
            self._mode_samples[mode] += 1
            return [DataSample(mode=mode, observation=observation, metadata={"foveated": False})]

        for i in range(max(1, int(self.config.foveation_samples))):
            # Deterministic-ish sampling based on step counter to keep tests stable
            y0 = (self._step_count + i * 13) % max(1, H - crop + 1)
            x0 = (self._step_count + i * 29) % max(1, W - crop + 1)
            view = obs[:, y0 : y0 + crop, x0 : x0 + crop]
            self._mode_samples[mode] += 1
            samples.append(
                DataSample(
                    mode=mode,
                    observation=view,
                    metadata={"y0": int(y0), "x0": int(x0), "crop": int(crop)},
                )
            )

        return samples

    def get_statistics(self) -> dict[str, Any]:
        """Return basic controller statistics."""
        return {
            "step_count": self._step_count,
            "mode_samples": {m.value: n for m, n in self._mode_samples.items()},
        }


# Singleton
_controller: DataStreamController | None = None


def get_data_stream_controller(config: DataStreamConfig | None = None) -> DataStreamController:
    """Get a shared DataStreamController instance."""
    global _controller
    if _controller is None or config is not None:
        _controller = DataStreamController(config)
    return _controller


__all__ = [
    "DataMode",
    "DataSample",
    "DataStreamConfig",
    "DataStreamController",
    "get_data_stream_controller",
]
