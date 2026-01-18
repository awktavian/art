"""Instruction → virtual action plan translator.

This module converts natural-language or LANG intents into a normalized plan
that can be replayed through HAL input controllers, motion primitives, and the
sensorimotor world model.

Note: Consolidated from kagami.core.embodied.instruction_translator
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from kagami_hal.input_controller import InputType
from kagami_observability.metrics.forge import EMBODIED_PLAN_GENERATIONS

from kagami.core.embodiment.motion_primitives import MotionType, get_primitive

logger = logging.getLogger(__name__)


PLAN_VERSION = "1.0"

_MOTION_KEYWORDS = {
    MotionType.RUN: {"run", "sprint", "dash", "hurry"},
    MotionType.WALK: {"walk", "move", "approach", "go", "travel", "navigate"},
    MotionType.JUMP: {"jump", "climb", "vault", "hop"},
    MotionType.DASH: {"evade", "dodge", "slide"},
    MotionType.ROLL: {"roll"},
    MotionType.PUNCH: {"attack", "strike", "punch", "hit"},
    MotionType.KICK: {"kick"},
    MotionType.GRAB: {"grab", "pick", "lift", "collect"},
    MotionType.THROW: {"throw", "launch", "toss"},
    MotionType.PUSH: {"push", "shove"},
    MotionType.PULL: {"pull", "drag"},
    MotionType.BLOCK: {"block", "guard", "defend"},
}

_DEFAULT_SEQUENCE = [MotionType.WALK]

_INPUT_TEMPLATES: dict[MotionType, list[dict[str, Any]]] = {
    MotionType.WALK: [
        {"type": InputType.KEYBOARD.value, "value": "KeyW", "duration_ms": 800, "speed": 1.0}
    ],
    MotionType.RUN: [
        {
            "type": InputType.KEYBOARD.value,
            "value": "KeyW",
            "modifiers": ["ShiftLeft"],
            "duration_ms": 600,
            "speed": 1.5,
        }
    ],
    MotionType.DASH: [
        {
            "type": InputType.KEYBOARD.value,
            "value": "KeyW",
            "modifiers": ["ShiftLeft"],
            "duration_ms": 200,
            "speed": 2.0,
        },
        {"type": InputType.KEYBOARD.value, "value": "KeySpace", "duration_ms": 120, "speed": 1.0},
    ],
    MotionType.JUMP: [{"type": InputType.KEYBOARD.value, "value": "KeySpace", "duration_ms": 150}],
    MotionType.ROLL: [{"type": InputType.KEYBOARD.value, "value": "KeyShift", "duration_ms": 250}],
    MotionType.GRAB: [
        {"type": InputType.MOUSE.value, "value": "Button1", "duration_ms": 120},
        {"type": InputType.KEYBOARD.value, "value": "KeyE", "duration_ms": 120},
    ],
    MotionType.THROW: [
        {"type": InputType.MOUSE.value, "value": "Button1", "duration_ms": 200},
        {"type": InputType.MOUSE.value, "value": "Button1", "duration_ms": 200},
    ],
    MotionType.PUNCH: [{"type": InputType.MOUSE.value, "value": "Button1", "duration_ms": 160}],
    MotionType.KICK: [
        {"type": InputType.MOUSE.value, "value": "Button1", "duration_ms": 160},
        {"type": InputType.KEYBOARD.value, "value": "KeyF", "duration_ms": 140},
    ],
    MotionType.BLOCK: [{"type": InputType.MOUSE.value, "value": "Button2", "duration_ms": 400}],
    MotionType.PUSH: [
        {"type": InputType.KEYBOARD.value, "value": "KeyE", "duration_ms": 250, "speed": 0.8}
    ],
    MotionType.PULL: [
        {"type": InputType.KEYBOARD.value, "value": "KeyQ", "duration_ms": 250, "speed": 0.8}
    ],
}


@dataclass
class VirtualActionStep:
    """Single step within a virtual action plan."""

    motion: str
    description: str
    reasoning: str
    inputs: list[dict[str, Any]] = field(default_factory=list[Any])
    metadata: dict[str, Any] = field(default_factory=dict[str, Any])

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": str(uuid.uuid4()),
            "motion": self.motion,
            "description": self.description,
            "reasoning": self.reasoning,
            "inputs": self.inputs,
            "metadata": self.metadata,
        }


def _normalize_intent_payload(intent_payload: Any) -> dict[str, Any]:
    if intent_payload is None:
        return {}
    if hasattr(intent_payload, "model_dump"):
        try:
            return intent_payload.model_dump(mode="json")  # type: ignore[no-any-return]
        except Exception:
            return intent_payload.model_dump()  # type: ignore[no-any-return]
    if isinstance(intent_payload, dict):
        return dict(intent_payload)
    try:
        return {"action": str(intent_payload)}
    except Exception:
        return {}


def _collect_keywords(payload: dict[str, Any], sections: dict[str, Any] | None) -> set[str]:
    tokens: set[str] = set()
    for key in ("action", "target", "goal"):
        value = payload.get(key)
        if isinstance(value, str):
            tokens.update(value.lower().split())
    metadata = payload.get("metadata") or {}
    if isinstance(metadata, dict):
        goal = metadata.get("goal")
        if isinstance(goal, str):
            tokens.update(goal.lower().split())
    if sections and isinstance(sections, dict):
        goal = sections.get("GOAL")
        if isinstance(goal, str):
            tokens.update(goal.lower().split())
    params = payload.get("parameters") or payload.get("params")
    if isinstance(params, dict):
        for val in params.values():
            if isinstance(val, str):
                tokens.update(val.lower().split())
    return tokens


def _select_motions(tokens: set[str]) -> list[MotionType]:
    matches: list[MotionType] = []
    for motion, keywords in _MOTION_KEYWORDS.items():
        if tokens.intersection(keywords):
            matches.append(motion)
    if not matches:
        return list(_DEFAULT_SEQUENCE)
    # Limit to 3 motions to keep plan concise
    pruned: list[MotionType] = []
    for motion in matches:
        if motion not in pruned:
            pruned.append(motion)
        if len(pruned) == 3:
            break
    return pruned


def _inputs_for_motion(motion: MotionType) -> list[dict[str, Any]]:
    template = _INPUT_TEMPLATES.get(motion)
    if template:
        return [dict(entry) for entry in template]
    primitive = get_primitive(motion)
    return [
        {
            "type": InputType.KEYBOARD.value,
            "value": motion.value,
            "duration_ms": int(primitive.duration * 1000),
        }
    ]


def _describe_motion(motion: MotionType, target: str | None) -> tuple[str, str]:
    if motion == MotionType.RUN:
        return ("swift approach", f"Run towards {target or 'the objective'} while keeping cover.")
    if motion == MotionType.JUMP:
        return ("vertical traversal", "Jump to gain verticality or clear an obstacle.")
    if motion == MotionType.DASH:
        return ("burst movement", "Dash to reposition quickly before executing the goal.")
    if motion == MotionType.PUNCH:
        return ("close-quarters strike", "Use a quick strike to interact or neutralize.")
    if motion == MotionType.GRAB:
        return ("object interaction", "Grab the relevant object or handle before proceeding.")
    if motion == MotionType.THROW:
        return (
            "projected interaction",
            "Throw or release the held item towards the target.",
        )
    return ("direct movement", f"Move deliberately toward {target or 'the objective'}.")


def _flatten_action_list(steps: Iterable[dict[str, Any]]) -> tuple[list[str], list[float]]:
    actions: list[str] = []
    speeds: list[float] = []
    for step in steps:
        for inp in step.get("inputs", []):
            if not isinstance(inp, dict):
                continue
            value = inp.get("value")
            if not isinstance(value, str):
                continue
            modifiers = inp.get("modifiers")
            if isinstance(modifiers, list) and modifiers:
                value_repr = "+".join([*modifiers, value])
            else:
                value_repr = value
            actions.append(value_repr)
            duration = inp.get("duration_ms")
            try:
                speeds.append(float(duration) / 1000.0 if duration is not None else 0.25)
            except Exception:
                speeds.append(0.25)
    return actions, speeds


def _augment_with_world_model(action_steps: list[dict[str, Any]]) -> dict[str, Any] | None:
    try:
        from kagami.core.world_model.service import get_world_model_service
    except Exception as exc:
        logger.debug("World model service unavailable: %s", exc)
        return None

    try:
        model = get_world_model_service().model
    except Exception as exc:
        logger.debug("World model unavailable: %s", exc)
        return None

    if model is None:
        return None

    summarizer = getattr(model, "summarize_plan", None)
    if callable(summarizer):
        try:
            return summarizer(action_steps)  # type: ignore[no-any-return]
        except Exception as exc:
            logger.debug("Sensorimotor summarize_plan failed: %s", exc)
            return None
    return None


def generate_virtual_action_plan(
    intent_payload: Any,
    *,
    sections: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a normalized virtual action plan."""
    status = "success"
    try:
        payload = _normalize_intent_payload(intent_payload)
        if not payload:
            return {
                "version": PLAN_VERSION,
                "plan_id": str(uuid.uuid4()),
                "summary": "No structured actions inferred.",
                "steps": [],
                "action_list": [],
                "action_speed_list": [],
            }

        target = payload.get("target")
        if isinstance(target, dict):
            target = target.get("name")

        tokens = _collect_keywords(payload, sections)
        motions = _select_motions(tokens)

        steps: list[dict[str, Any]] = []
        for motion in motions:
            label, reasoning = _describe_motion(motion, target)
            step = VirtualActionStep(
                motion=motion.value,
                description=label,
                reasoning=reasoning,
                inputs=_inputs_for_motion(motion),
                metadata={"motion_type": motion.value},
            )
            steps.append(step.as_dict())

        action_list, action_speed_list = _flatten_action_list(steps)
        plan_summary = f"Execute {' → '.join(step['motion'] for step in steps)} to accomplish {target or 'goal'}."

        plan = {
            "version": PLAN_VERSION,
            "plan_id": str(uuid.uuid4()),
            "summary": plan_summary,
            "target": target,
            "steps": steps,
            "action_list": action_list,
            "action_speed_list": action_speed_list,
        }

        goal = payload.get("goal")
        metadata = payload.get("metadata")
        if not goal and isinstance(metadata, dict):
            goal = metadata.get("goal")
        if goal:
            plan["goal"] = goal

        predictions = _augment_with_world_model(steps)
        if predictions:
            plan["predictions"] = predictions

        return plan
    except Exception:
        status = "error"
        raise
    finally:
        try:
            EMBODIED_PLAN_GENERATIONS.labels(status=status).inc()
        except Exception:
            pass


__all__ = ["VirtualActionStep", "generate_virtual_action_plan"]
