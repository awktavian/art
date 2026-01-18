from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def is_complex(context: dict[str, Any]) -> bool:
    return bool(
        context.get("multi_step") or context.get("cross_files") or context.get("uncertainty")
    )


@dataclass
class Plan:
    goal: str
    steps: list[str]
    evidence: list[str]
    done_criteria: list[str]


def narrate(goal: str) -> Plan:
    steps = [
        "Understand current state",
        "Propose minimal change",
        "Implement and test",
    ]
    evidence = ["Tests green", "Lint clean"]
    done = ["All steps complete", "CI passes"]
    return Plan(goal=goal, steps=steps, evidence=evidence, done_criteria=done)


__all__ = ["Plan", "is_complex", "narrate"]
