from __future__ import annotations

from kagami.boot import BootNode
from kagami.boot.actions import (
    startup_background_tasks,
    startup_brain,
    startup_learning_systems,
)
from kagami.boot.actions.wiring import startup_voice_warmup
from kagami.boot.nodes import health_flag


def get_background_nodes() -> list[BootNode]:
    """Return background task boot nodes (brain, background tasks, learning, voice).

    OPTIMIZED (Dec 28, 2025): All run in PARALLEL after orchestrator.
    - brain: Matryoshka Brain API (~2s)
    - background: Task manager + autonomous engine (~3s)
    - learning: Learning loop + coordinator (~2s)
    - voice: Parler-TTS warmup (~3s) - enables low-latency announcements
    """
    return [
        BootNode(
            name="brain",
            start=startup_brain,
            dependencies=("orchestrator",),
            health_check=health_flag("brain_api", "brain_ready"),
            timeout_s=5.0,
        ),
        BootNode(
            name="background",
            start=startup_background_tasks,
            dependencies=("orchestrator",),
            health_check=health_flag("background_task_manager", "background_tasks_ready"),
            timeout_s=30.0,  # Increased: autonomous goal engine capability discovery
        ),
        BootNode(
            name="learning",
            start=startup_learning_systems,
            dependencies=("orchestrator",),
            health_check=health_flag("learning_systems_ready", "learning_systems_ready"),
            timeout_s=5.0,
        ),
        BootNode(
            name="voice",
            start=startup_voice_warmup,
            dependencies=("ambient_os",),  # Voice warmup after ambient OS
            health_check=health_flag("voice_module", "voice_ready"),
            timeout_s=120.0,  # Parler-TTS model load can take time (extended for cold boot)
        ),
    ]
