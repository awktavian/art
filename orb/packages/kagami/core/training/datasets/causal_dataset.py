"""Base class for causal datasets.

Provides a common interface for datasets that produce causal trajectories
(state_t, action_t, state_t_plus_1) for world model training.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Any

from torch.utils.data import IterableDataset


class CausalDataset(IterableDataset):
    """Base class for causal trajectory datasets.

    All causal datasets should produce samples with at minimum:
    - state_t: Current state tensor [T, D]
    - action_t: Action tensor [T, A]
    - state_t_plus_1: Next state tensor [T, D]

    Subclasses implement __iter__ to yield these samples.
    """

    @abstractmethod
    def __iter__(self):
        """Yield causal trajectory samples."""
        ...

    def __getitem__(self, idx: int) -> dict[str, Any]:
        """Index access (optional, for compatibility).

        Default implementation iterates to the index.
        Override for efficient random access if available.
        """
        it = iter(self)
        for _ in range(max(0, int(idx))):
            next(it)
        return next(it)
