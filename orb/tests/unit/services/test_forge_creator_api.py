from __future__ import annotations

import pytest

from kagami.core.exceptions import ValidationError
from kagami.forge.creator_api import parse_genesis_video_spec


def test_parse_genesis_video_spec_template_minimal() -> None:
    spec = parse_genesis_video_spec(
        {
            "template": "physics_diversity",
            "output_dir": "/tmp/forge_creator_test",
        }
    )
    assert spec.output_dir
    assert spec.name == "physics_diversity"
    assert len(spec.entities) > 0


def test_parse_genesis_video_spec_explicit_minimal_entities() -> None:
    spec = parse_genesis_video_spec(
        {
            "output_dir": "/tmp/forge_creator_test",
            "name": "custom",
            "preset": "proof",
            "duration": 1.0,
            "entities": [
                {
                    "name": "glass_box",
                    "solver": "rigid",
                    "shape": "box",
                    "position": [0, 0, 0.2],
                    "size": [0.2, 0.2, 0.2],
                    "material_preset": "glass",
                    "surface": {"ior": 1.52, "subsurface": True, "thickness": 0.02},
                }
            ],
            "raytracer": {"tracing_depth": 12, "rr_depth": 3, "light": [{"pos": [2, -2, 3]}]},
        }
    )
    assert spec.name == "custom"
    assert spec.entities[0].name == "glass_box"
    assert spec.raytracer is not None


def test_parse_genesis_video_spec_rejects_missing_output_dir() -> None:
    with pytest.raises(ValidationError):
        parse_genesis_video_spec({"template": "material_showcase"})
