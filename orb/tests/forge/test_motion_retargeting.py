"""Tests for kagami.forge.modules.motion.motion_retargeting."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock
import numpy as np

from kagami.forge.modules.motion.motion_retargeting import (
    BoneTransform,
    MotionFrame,
    MotionClip,
)

pytestmark = pytest.mark.tier_unit


class TestBoneTransform:
    """Test BoneTransform dataclass."""

    def test_create_bone_transform(self):
        """Test creating a BoneTransform."""
        transform = BoneTransform(
            position=np.array([0, 0, 0]),
            rotation=np.array([0, 0, 0, 1]),
            scale=np.array([1, 1, 1]),
        )

        assert transform.position.shape == (3,)
        assert transform.rotation.shape == (4,)

class TestMotionFrame:
    """Test MotionFrame dataclass."""

    def test_create_motion_frame(self):
        """Test creating a MotionFrame."""
        transforms = {
            "root": BoneTransform(
                position=np.array([0, 0, 0]),
                rotation=np.array([0, 0, 0, 1]),
                scale=np.array([1, 1, 1]),
            )
        }

        frame = MotionFrame(timestamp=0.0, transforms=transforms)
        assert frame.timestamp == 0.0
        assert "root" in frame.transforms
