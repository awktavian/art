"""Regression tests for Genesis curriculum integration.

These tests ensure Genesis puzzles are always available (no silent skipping),
and that CurriculumDataset + collate_fn produce valid temporal tensors.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration

from pathlib import Path

import torch

from kagami.core.config.unified_config import TrainingConfig as PretrainConfig
from kagami.core.training.real_data_loader import create_curriculum_dataloader


def test_curriculum_dataloader_includes_genesis_even_without_local_data(tmp_path: Path) -> None:
    """Even with an empty data_root, Genesis should provide an infinite stream."""
    cfg = PretrainConfig(
        model_preset="minimal",
        student_dim=32,
        sequence_length=8,
        batch_size=2,
        max_samples=32,
        device="cpu",
        num_workers=0,
        use_curriculum=True,
    )

    loader = create_curriculum_dataloader(cfg, phase="hierarchy", data_root=tmp_path)

    # Force Genesis / JEPA sampling.
    loader.dataset.set_phase("hierarchy")  # type: ignore[attr-defined]
    loader.dataset.set_sampling_weights({"jepa": 1.0})  # type: ignore[attr-defined]

    batch = next(iter(loader))

    assert isinstance(batch, dict)
    assert batch.get("source") == ["jepa", "jepa"]

    state_t = batch["state_t"]
    state_tp1 = batch["state_t_plus_1"]
    action_t = batch["action_t"]

    assert isinstance(state_t, torch.Tensor)
    assert isinstance(state_tp1, torch.Tensor)
    assert isinstance(action_t, torch.Tensor)

    # [B, T, D]
    assert tuple(state_t.shape[:2]) == (2, 8)
    assert state_t.shape[2] == 32
    assert tuple(state_tp1.shape) == tuple(state_t.shape)

    # [B, T, A]
    assert tuple(action_t.shape[:2]) == (2, 8)
    assert action_t.shape[2] == 8
