"""Operation Recording Mode - Full Context Capture for Replay.

When KAGAMI_RECORD_OPERATIONS=1, saves complete context for deterministic replay.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class OperationRecorder:
    """Records full operation context for replay."""

    def __init__(self) -> None:
        self.enabled = os.getenv("KAGAMI_RECORD_OPERATIONS", "0") == "1"
        self.output_dir = Path("artifacts/recordings")
        if self.enabled:
            self.output_dir.mkdir(parents=True, exist_ok=True)

    def record(self, correlation_id: str, data: dict[str, Any]) -> None:
        """Append to recording file."""
        if not self.enabled:
            return

        try:
            file_path = self.output_dir / f"{correlation_id}.jsonl"
            with open(file_path, "a") as f:
                f.write(json.dumps(data) + "\n")
        except Exception as e:
            logger.debug(f"Recording failed: {e}")

    def record_prompt(
        self, correlation_id: str, prompt: str, enhanced_prompt: str | None = None
    ) -> None:
        """Record prompt (original + enhanced)."""
        self.record(
            correlation_id,
            {
                "type": "prompt",
                "original": prompt,
                "enhanced": enhanced_prompt,
                "timestamp": __import__("time").time(),
            },
        )

    def record_embedding(self, correlation_id: str, text: str, embedding: Any) -> None:
        """Record embedding."""
        self.record(
            correlation_id,
            {
                "type": "embedding",
                "text": text,
                "embedding": (
                    embedding.tolist() if hasattr(embedding, "tolist") else list(embedding)
                ),
                "timestamp": __import__("time").time(),
            },
        )

    def record_rl_state(
        self, correlation_id: str, state: Any, action: dict[str, Any], candidates: list[Any]
    ) -> None:
        """Record RL state and decision."""
        self.record(
            correlation_id,
            {
                "type": "rl_decision",
                "state": str(state),
                "action": action,
                "candidates": candidates,
                "timestamp": __import__("time").time(),
            },
        )

    def record_tool_output(
        self, correlation_id: str, tool: str, args: dict[str, Any], output: Any
    ) -> None:
        """Record tool call and output."""
        self.record(
            correlation_id,
            {
                "type": "tool_output",
                "tool": tool,
                "args": args,
                "output": str(output)[:1000],  # Truncate large outputs
                "timestamp": __import__("time").time(),
            },
        )


_recorder: OperationRecorder | None = None


def get_recorder() -> OperationRecorder:
    """Get singleton recorder."""
    global _recorder
    if _recorder is None:
        _recorder = OperationRecorder()
    return _recorder
