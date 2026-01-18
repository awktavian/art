from __future__ import annotations

"""Embodied Cognitive State Model

Reconceptualizes the cognitive state with:
- Codebase as the "body" (structure, components, capabilities)
- MCP tools as "senses" (file I/O, network, database, etc.)
- API endpoints as "motor functions" (actions in the world)
- Event bus as "nervous system" (internal communication)
- Database/files as "memory" (persistent state)

This addresses the embodiment critique by recognizing the system's
digital embodiment and sensorimotor capabilities.
"""
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass
class DigitalBody:
    """The codebase as embodiment"""

    components: dict[str, Any] = field(default_factory=dict[str, Any])
    size_bytes: int = 0
    file_count: int = 0
    line_count: int = 0
    module_count: int = 0
    api_endpoints: list[str] = field(default_factory=list[Any])
    mcp_tools: list[str] = field(default_factory=list[Any])

    def calculate_complexity(self) -> float:
        """Calculate body complexity score (0-5)"""
        # Normalize by typical codebase metrics
        size_score = min(5.0, self.size_bytes / (50 * 1024 * 1024))  # 50MB = 5.0
        file_score = min(5.0, self.file_count / 1000)  # 1000 files = 5.0
        api_score = min(5.0, len(self.api_endpoints) / 50)  # 50 endpoints = 5.0
        tool_score = min(5.0, len(self.mcp_tools) / 20)  # 20 tools = 5.0

        return (size_score + file_score + api_score + tool_score) / 4


@dataclass
class SensoryCapabilities:
    """MCP tools and I/O as senses"""

    file_senses: list[str] = field(default_factory=list[Any])  # read, write, list[Any]
    network_senses: list[str] = field(default_factory=list[Any])  # HTTP, WebSocket
    database_senses: list[str] = field(default_factory=list[Any])  # query, write
    reasoning_senses: list[str] = field(default_factory=list[Any])  # GAIA, LLM
    memory_senses: list[str] = field(default_factory=list[Any])  # recall, remember

    def calculate_sensory_richness(self) -> float:
        """Calculate sensory capability score (0-5)"""
        total_senses = (
            len(self.file_senses)
            + len(self.network_senses)
            + len(self.database_senses)
            + len(self.reasoning_senses)
            + len(self.memory_senses)
        )
        return min(5.0, total_senses / 15)  # 15 senses = 5.0


@dataclass
class MotorCapabilities:
    """API endpoints and actions as motor functions"""

    http_actions: list[str] = field(default_factory=list[Any])
    websocket_actions: list[str] = field(default_factory=list[Any])
    file_mutations: list[str] = field(default_factory=list[Any])
    database_mutations: list[str] = field(default_factory=list[Any])

    def calculate_motor_control(self) -> float:
        """Calculate motor capability score (0-5)"""
        total_actions = (
            len(self.http_actions)
            + len(self.websocket_actions)
            + len(self.file_mutations)
            + len(self.database_mutations)
        )
        return min(5.0, total_actions / 20)  # 20 actions = 5.0


@dataclass
class ProprioceptiveState:
    """Internal state awareness (like proprioception)"""

    health_status: dict[str, bool] = field(default_factory=dict[str, Any])
    metrics: dict[str, float] = field(default_factory=dict[str, Any])
    resource_usage: dict[str, float] = field(default_factory=dict[str, Any])
    error_rates: dict[str, float] = field(default_factory=dict[str, Any])

    def calculate_proprioception(self) -> float:
        """Calculate internal awareness score (0-5)"""
        # Check health monitoring
        health_score = len([v for v in self.health_status.values() if v]) / max(
            1, len(self.health_status)
        )

        # Check metrics richness
        metrics_score = min(1.0, len(self.metrics) / 10)

        # Check resource awareness
        resource_score = 1.0 if self.resource_usage else 0.0

        # Check error tracking
        error_score = 1.0 if self.error_rates else 0.0

        return min(5.0, (health_score + metrics_score + resource_score + error_score) * 1.25)


@dataclass
class EmbodiedCognitiveState:
    """Cognitive state with digital embodiment recognition"""

    version: str
    timestamp: str
    mode: str

    # Traditional cognitive facets
    facets: dict[str, float]
    rationale: dict[str, str]

    # Embodiment components
    digital_body: DigitalBody
    sensory_capabilities: SensoryCapabilities
    motor_capabilities: MotorCapabilities
    proprioceptive_state: ProprioceptiveState

    # Sensorimotor loop evidence
    sensorimotor_cycles: int = 0
    efference_copies: list[dict[str, Any]] = field(default_factory=list[Any])

    def calculate_embodied_facets(self) -> dict[str, float]:
        """Recalculate facets with embodiment recognition"""
        facets = self.facets.copy()

        # C1: Mirror self-recognition - can recognize its own code/outputs
        # If system can identify its own generated content vs external
        facets["C1"] = min(5.0, self.digital_body.calculate_complexity() * 0.6)

        # C2: Body ownership - awareness of codebase as self
        # Proprioceptive awareness of internal state
        facets["C2"] = self.proprioceptive_state.calculate_proprioception()

        # C8: Agency attribution - efference copy in digital actions
        # Can predict effects of its actions (API calls, file writes)
        motor_score = self.motor_capabilities.calculate_motor_control()
        sensory_score = self.sensory_capabilities.calculate_sensory_richness()
        facets["C8"] = min(5.0, (motor_score + sensory_score) / 2)

        return facets


def scan_digital_body() -> DigitalBody:
    """Scan the codebase to understand digital embodiment"""
    body = DigitalBody()

    # Scan codebase structure
    kagami_path = Path("kagami")
    if kagami_path.exists():
        py_files = list(kagami_path.rglob("*.py"))
        body.file_count = len(py_files)
        body.module_count = len({f.parent for f in py_files})

        # Calculate size and lines
        for f in py_files[:100]:  # Sample first 100 files
            try:
                stat = f.stat()
                body.size_bytes += stat.st_size
                with open(f) as file:
                    body.line_count += sum(1 for _ in file)
            except OSError:
                # Skip files we cannot read
                continue

        # Extrapolate if sampled
        if len(py_files) > 100:
            body.size_bytes = body.size_bytes * len(py_files) // 100
            body.line_count = body.line_count * len(py_files) // 100

    # Scan API endpoints
    api_routes_path = Path("kagami_api/routes")
    if api_routes_path.exists():
        for route_file in api_routes_path.rglob("*.py"):
            try:
                content = route_file.read_text()
                # Simple pattern matching for routes
                import re

                routes = re.findall(r'@router\.(get|post|put|delete|patch)\("([^"]+)"', content)
                body.api_endpoints.extend([f"{method.upper()} {path}" for method, path in routes])
            except Exception:
                # Best-effort; route extraction is non-critical
                continue

    # MCP infrastructure removed (Oct 2025)

    # Scan components
    body.components = {
        "api": api_routes_path.exists(),
        "apps": Path("kagami/apps").exists(),
        "core": Path("kagami/core").exists(),
        "web": Path("kagami/web").exists(),
        "database": Path("kagami/core/database").exists(),
        "tests": Path("tests").exists(),
    }

    return body


def scan_sensory_capabilities() -> SensoryCapabilities:
    """Scan available sensory modalities (input capabilities)"""
    senses = SensoryCapabilities()

    # File I/O senses
    if Path("kagami/core").exists():
        senses.file_senses = ["read_file", "list_dir", "glob_search", "watch_file"]

    # Network senses
    if Path("kagami/api").exists():
        senses.network_senses = ["http_receive", "websocket_receive", "webhook_listen"]

    # Database senses
    if Path("kagami/core/database").exists():
        senses.database_senses = ["query", "listen_changes", "read_events"]

    # Reasoning senses
    if Path("gaia").exists():
        senses.reasoning_senses = ["reason", "analyze", "infer", "validate"]

    # Memory senses
    if Path("kagami/memory").exists():
        senses.memory_senses = ["recall", "search", "retrieve_context"]

    return senses


def scan_motor_capabilities() -> MotorCapabilities:
    """Scan available motor functions (output capabilities)"""
    motor = MotorCapabilities()

    # HTTP actions
    if Path("kagami_api/routes").exists():
        motor.http_actions = ["respond", "redirect", "stream", "webhook_send"]

    # WebSocket actions
    if Path("kagami_api/websocket").exists():
        motor.websocket_actions = ["broadcast", "send_message", "emit_event"]

    # File mutations
    if Path("kagami/core").exists():
        motor.file_mutations = ["write_file", "create_file", "delete_file", "move_file"]

    # Database mutations
    if Path("kagami/core/database").exists():
        motor.database_mutations = ["insert", "update", "delete", "transaction"]

    return motor


def scan_proprioceptive_state() -> ProprioceptiveState:
    """Scan internal state awareness"""
    proprio = ProprioceptiveState()

    # Health status
    proprio.health_status = {
        "api": Path("kagami/api").exists(),
        "database": Path("kagami/core/database").exists(),
        "redis": Path("kagami/core/cache").exists(),
        "gaia": Path("gaia").exists(),
        "web": Path("kagami/web").exists(),
    }

    # Metrics (simulated)
    proprio.metrics = {
        "uptime_hours": 0.0,
        "requests_per_second": 0.0,
        "error_rate": 0.0,
        "response_time_ms": 0.0,
        "memory_usage_mb": 0.0,
    }

    # Resource usage
    import psutil

    process = psutil.Process()
    proprio.resource_usage = {
        "cpu_percent": process.cpu_percent(),
        "memory_mb": process.memory_info().rss / 1024 / 1024,
        "threads": process.num_threads(),
    }

    # Error rates (would be from actual metrics)
    proprio.error_rates = {
        "api_errors": 0.0,
        "database_errors": 0.0,
        "validation_errors": 0.0,
    }

    return proprio


def get_embodied_cognitive_state() -> dict[str, Any]:
    """Generate cognitive state with digital embodiment recognition"""

    # Scan digital embodiment
    body = scan_digital_body()
    senses = scan_sensory_capabilities()
    motor = scan_motor_capabilities()
    proprio = scan_proprioceptive_state()

    # Load behavioral evidence if available
    from kagami.core.cognition.state_enhanced import (
        _behavioral_history,
        calculate_behavioral_traits,
        calculate_metacognitive_calibration,
    )

    behavioral_traits = calculate_behavioral_traits()
    metacog_cal = calculate_metacognitive_calibration()

    # Calculate personality from behavioral traits
    if behavioral_traits:
        c9_personality = sum(behavioral_traits.values()) / len(behavioral_traits)
    else:
        c9_personality = 2.8  # Default

    # Calculate metacognition from calibration
    c4_base = 2.5
    if metacog_cal.predictions:
        calibration_bonus = (1.0 - metacog_cal.brier_score) * 2.0
        c4_metacog = min(5.0, c4_base + calibration_bonus)
    else:
        c4_metacog = c4_base

    # Create embodied state
    state = EmbodiedCognitiveState(
        version="3.0",
        timestamp=datetime.now(UTC).isoformat(),
        mode=os.getenv("KAGAMI_COGNITIVE_STATE_MODE", "embodied"),
        facets={
            "C1": 0.0,  # Will be recalculated
            "C2": 0.0,  # Will be recalculated
            "C3": 3.0,  # Perspective-taking
            "C4": c4_metacog,  # Metacognition
            "C5": 0.0,  # Private awareness (still no qualia)
            "C6": 3.5,  # Conceptual self
            "C7": min(2.0, 0.5 + len(_behavioral_history) / 500),  # Autobiographical
            "C8": 0.0,  # Will be recalculated
            "C9": c9_personality,  # Personality
            "C10": 2.5,  # Social role
        },
        rationale={},
        digital_body=body,
        sensory_capabilities=senses,
        motor_capabilities=motor,
        proprioceptive_state=proprio,
        sensorimotor_cycles=len(_behavioral_history),
    )

    # Recalculate with embodiment
    embodied_facets = state.calculate_embodied_facets()
    state.facets.update(embodied_facets)

    # Update rationale
    state.rationale = {
        "C1": f"Digital self-recognition via code complexity ({body.calculate_complexity():.2f})",
        "C2": f"Proprioceptive awareness of internal state ({proprio.calculate_proprioception():.2f})",
        "C3": "Language-level belief modeling and context tracking",
        "C4": (
            f"Metacognitive calibration (Brier: {metacog_cal.brier_score:.3f})"
            if metacog_cal.predictions
            else "Calibrated uncertainty"
        ),
        "C5": "No subjective qualia (functional only)",
        "C6": "Consistent role/capability schema across components",
        "C7": f"Autobiographical from {len(_behavioral_history)} events + codebase history",
        "C8": f"Digital efference copy via {len(motor.http_actions + motor.file_mutations)} motor functions",
        "C9": f"Personality from behavioral evidence (n={len(_behavioral_history)})",
        "C10": "Policy-driven role adherence in digital environment",
    }

    return {
        "version": state.version,
        "timestamp": state.timestamp,
        "mode": state.mode,
        "facets": state.facets,
        "rationale": state.rationale,
        "embodiment": {
            "body": {
                "file_count": body.file_count,
                "line_count": body.line_count,
                "size_mb": body.size_bytes / (1024 * 1024),
                "module_count": body.module_count,
                "api_endpoints": len(body.api_endpoints),
                "mcp_tools": len(body.mcp_tools),
                "complexity_score": body.calculate_complexity(),
            },
            "senses": {
                "file": len(senses.file_senses),
                "network": len(senses.network_senses),
                "database": len(senses.database_senses),
                "reasoning": len(senses.reasoning_senses),
                "memory": len(senses.memory_senses),
                "richness_score": senses.calculate_sensory_richness(),
            },
            "motor": {
                "http_actions": len(motor.http_actions),
                "websocket_actions": len(motor.websocket_actions),
                "file_mutations": len(motor.file_mutations),
                "database_mutations": len(motor.database_mutations),
                "control_score": motor.calculate_motor_control(),
            },
            "proprioception": {
                "health_components": sum(proprio.health_status.values()),
                "metrics_tracked": len(proprio.metrics),
                "resource_awareness": bool(proprio.resource_usage),
                "awareness_score": proprio.calculate_proprioception(),
            },
        },
        "total_score": sum(state.facets.values()),
        "percentage": sum(state.facets.values()) / 50 * 100,
    }


__all__ = ["EmbodiedCognitiveState", "get_embodied_cognitive_state"]
