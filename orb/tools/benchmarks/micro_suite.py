"""Micro-Benchmark Suite for K os (Real Orchestrator Calls).

All tasks below execute real intents via the IntentOrchestrator. No sleeps, no fakes.
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Any

from kagami.core.orchestrator import IntentOrchestrator


class BenchmarkTask:
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    async def run(
        self, orchestrator: IntentOrchestrator, metadata: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute this benchmark task.

        Args:
            orchestrator: Intent orchestrator to execute against
            metadata: Benchmark metadata (strategy, settings, etc.)

        Returns:
            Dictionary with benchmark results:
            - success: bool - Whether the task succeeded
            - duration_ms: int - Execution time in milliseconds
            - error: Optional error information
            - Additional task-specific metrics

        Raises:
            NotImplementedError: Must be implemented by subclasses
        """
        raise NotImplementedError(
            f"{self.__class__.__name__}.run() must be implemented to define "
            "the specific benchmark task logic"
        )


class ChatSimple(BenchmarkTask):
    def __init__(self):
        super().__init__(name="chat_simple", description="Simple chat intent roundtrip")

    async def run(
        self, orchestrator: IntentOrchestrator, metadata: dict[str, Any]
    ) -> dict[str, Any]:
        start = time.time()
        intent = {
            "action": "chat.send",
            "params": {"message": "Ping"},
            "metadata": metadata,
        }
        result = await orchestrator.process_intent(intent)
        duration_ms = int((time.time() - start) * 1000)
        return {
            "success": str(result.get("status", "")).lower() in {"accepted", "success"},
            "duration_ms": duration_ms,
            "response_len": len(str(result.get("response", ""))),
            "error": (
                None if str(result.get("status", "")).lower() in {"accepted", "success"} else result
            ),
        }


class FilesSearch(BenchmarkTask):
    def __init__(self):
        super().__init__(name="files_search", description="Search python files via files.search")

    async def run(
        self, orchestrator: IntentOrchestrator, metadata: dict[str, Any]
    ) -> dict[str, Any]:
        start = time.time()
        intent = {
            "app": "files",
            "action": "search",
            "params": {"pattern": "*.py", "limit": 10},
            "metadata": metadata,
        }
        result = await orchestrator.process_intent(intent)
        duration_ms = int((time.time() - start) * 1000)
        return {
            "success": str(result.get("status", "")).lower() in {"accepted", "success"},
            "duration_ms": duration_ms,
            "found": len(json.dumps(result)) if isinstance(result, dict) else 0,
            "error": (
                None if str(result.get("status", "")).lower() in {"accepted", "success"} else result
            ),
        }


class PlansCreate(BenchmarkTask):
    def __init__(self):
        super().__init__(name="plans_create", description="Create a simple plan via plans.create")

    async def run(
        self, orchestrator: IntentOrchestrator, metadata: dict[str, Any]
    ) -> dict[str, Any]:
        start = time.time()
        intent = {
            "app": "plans",
            "action": "create",
            "params": {"goal": "Add unit test for edge case"},
            "metadata": metadata,
        }
        result = await orchestrator.process_intent(intent)
        duration_ms = int((time.time() - start) * 1000)
        return {
            "success": str(result.get("status", "")).lower() in {"accepted", "success"},
            "duration_ms": duration_ms,
            "plan_len": len(json.dumps(result)) if isinstance(result, dict) else 0,
            "error": (
                None if str(result.get("status", "")).lower() in {"accepted", "success"} else result
            ),
        }


# Registry of real tasks
TASKS = [
    ChatSimple(),
    FilesSearch(),
    PlansCreate(),
]


async def run_suite(output_file: str | None = None) -> dict[str, Any]:
    orchestrator = IntentOrchestrator()
    await orchestrator.initialize()

    # Optional: toggle via env for ablation; fallback to safe defaults
    import os

    rl_on = os.getenv("RL_ON", "1") == "1"

    metadata: dict[str, Any] = {}
    # Set strategy hint for RL (baseline vs enhanced)
    if rl_on:
        metadata["strategy"] = "self_consistency_k3"
    else:
        metadata["strategy"] = "single_shot"

    # Strange loops are always on now; env toggles removed

    results = []
    for task in TASKS:
        r = await task.run(orchestrator, metadata)
        r["task"] = task.name
        r["description"] = task.description
        results.append(r)

    total_duration = sum(r["duration_ms"] for r in results)
    success_rate = sum(1 for r in results if r["success"]) / len(results)

    output = {
        "timestamp": int(time.time()),
        "summary": {
            "total_duration_ms": total_duration,
            "success_rate": success_rate,
            "tasks_succeeded": sum(1 for r in results if r["success"]),
            "tasks_total": len(results),
        },
        "results": results,
    }

    if output_file:
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w") as f:
            json.dump(output, f, indent=2)
        print(f"Results saved to {output_file}")

    return output


if __name__ == "__main__":
    asyncio.run(run_suite())
