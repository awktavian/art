
from __future__ import annotations


import os
from pathlib import Path

from kagami.core.learning.feedback import FeedbackEvent, emit_feedback


def test_feedback_written_and_dedup(tmp_path: Path):
    os.environ["KAGAMI_DATASET_DIR"] = str(tmp_path)
    evt = FeedbackEvent(thumb="up", app="plans", action="plan.create", rationale="ok")
    emit_feedback(evt, source="test")
    emit_feedback(evt, source="test")  # duplicate
    ds = tmp_path / "preferences.jsonl"
    assert ds.exists()
    contents = ds.read_text("utf-8").strip().splitlines()
    assert len(contents) == 1
    # cleanup env
    if "KAGAMI_DATASET_DIR" in os.environ:
        del os.environ["KAGAMI_DATASET_DIR"]
