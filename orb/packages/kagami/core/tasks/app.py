"""
Celery application configuration for K os.

Note: Celery is optional. When KAGAMI_REQUIRE_CELERY is not set[Any] (non-production),
imports should not crash the system. Prefer a single orchestration path; when
Temporal is used exclusively, this module can be removed.
"""

import logging
import os
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CeleryConfig:
    """Celery configuration."""

    broker_url: str = "redis://localhost:6379/0"
    result_backend: str = "redis://localhost:6379/1"
    task_serializer: str = "json"
    accept_content: list[Any] | None = None
    result_serializer: str = "json"
    timezone: str = "UTC"
    enable_utc: bool = True
    worker_prefetch_multiplier: int = 4
    worker_max_tasks_per_child: int = 1000
    task_acks_late: bool = True
    task_reject_on_worker_lost: bool = True
    task_default_retry_delay: int = 60
    task_max_retries: int = 3
    task_soft_time_limit: int = 600
    task_time_limit: int = 720
    result_expires: int = 3600
    result_persistent: bool = True
    worker_send_task_events: bool = True
    task_send_sent_event: bool = True

    def __post_init__(self) -> None:
        if self.accept_content is None:
            self.accept_content = ["json", "msgpack"]


config = CeleryConfig(
    broker_url=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    result_backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1"),
)


try:
    from celery import Celery
    from celery.schedules import crontab
    from kombu import Exchange, Queue

    _CELERY_AVAILABLE = True
except ModuleNotFoundError as exc:  # pragma: no cover - depends on environment
    # CI / lightweight dev installs may not include Celery.
    # This module MUST remain importable when Celery is optional.
    _CELERY_AVAILABLE = False
    logger.warning("Celery not installed; using no-op celery_app (tasks disabled): %s", exc)


class _NoopCeleryApp:
    """Minimal Celery-like façade used when Celery isn't installed."""

    def __init__(self, name: str = "kagami") -> None:
        self.main = name
        # Mirror a subset of Celery's conf API used by the codebase.
        self.conf = SimpleNamespace(
            imports=(),
            task_routes={},
            task_queues=(),
            beat_schedule={},
        )

    def task(self, *args: Any, **kwargs: Any) -> Any:
        # Signature compatible with Celery's @app.task decorator.
        from collections.abc import Callable

        def decorator(fn: Any) -> Callable[..., Any]:
            return fn  # type: ignore[no-any-return]

        return decorator

    def config_from_object(self, _obj: Any) -> None:
        return

    def autodiscover_tasks(self, _packages: list[str]) -> None:
        return


celery_app = Celery("kagami") if _CELERY_AVAILABLE else _NoopCeleryApp("kagami")
celery_app.config_from_object(config)

if _CELERY_AVAILABLE:
    _base_imports = tuple(celery_app.conf.imports or ())
    _required_imports = (
        "kagami.core.tasks.tasks",
        "kagami.core.tasks.processing_state",
    )
    celery_app.conf.imports = tuple(dict[str, Any].fromkeys(_base_imports + _required_imports))
    celery_app.conf.task_routes = {
        "kagami.core.tasks.tasks.process_intent_task": {"queue": "high_priority"},
        "kagami.core.tasks.tasks.generate_analytics_task": {"queue": "analytics"},
        "kagami.core.tasks.tasks.rollup_tenant_usage_task": {"queue": "analytics"},
        "kagami.core.tasks.tasks.rollup_marketplace_payouts_task": {"queue": "analytics"},
        "kagami.core.tasks.tasks.cleanup_expired_data_task": {"queue": "maintenance"},
        "kagami.core.tasks.tasks.sync_embeddings_task": {"queue": "ml"},
        "kagami.core.tasks.tasks.health_check_task": {"queue": "monitoring"},
    }
    celery_app.conf.task_queues = (
        Queue("high_priority", Exchange("high_priority"), routing_key="high_priority", priority=10),
        Queue("default", Exchange("default"), routing_key="default", priority=5),
        Queue("analytics", Exchange("analytics"), routing_key="analytics", priority=3),
        Queue("ml", Exchange("ml"), routing_key="ml", priority=3),
        Queue("background", Exchange("background"), routing_key="background", priority=2),
        Queue("maintenance", Exchange("maintenance"), routing_key="maintenance", priority=1),
        Queue("monitoring", Exchange("monitoring"), routing_key="monitoring", priority=1),
    )
    celery_app.conf.beat_schedule = {
        "cleanup-expired-data": {
            "task": "kagami.core.tasks.tasks.cleanup_expired_data_task",
            "schedule": crontab(hour=2, minute=0),
            "options": {"queue": "maintenance"},
        },
        "sync-embeddings": {
            "task": "kagami.core.tasks.tasks.sync_embeddings_task",
            "schedule": crontab(minute="*/30"),
            "options": {"queue": "ml"},
        },
        "health-check": {
            "task": "kagami.core.tasks.tasks.health_check_task",
            "schedule": 60.0,
            "options": {"queue": "monitoring"},
        },
        "generate-daily-analytics": {
            "task": "kagami.core.tasks.tasks.generate_analytics_task",
            "schedule": crontab(hour=6, minute=0),
            "kwargs": {"report_type": "daily"},
            "options": {"queue": "analytics"},
        },
        "rollup-tenant-usage": {
            "task": "kagami.core.tasks.tasks.rollup_tenant_usage_task",
            # Keep TenantUsage near-real-time; also finalizes prior month over time.
            "schedule": crontab(hour=1, minute=5),
            "kwargs": {"lookback_months": 2},
            "options": {"queue": "analytics"},
        },
        "rollup-marketplace-payouts": {
            "task": "kagami.core.tasks.tasks.rollup_marketplace_payouts_task",
            # Monthly payout computation - run on 2nd of each month for prior month
            "schedule": crontab(day_of_month=2, hour=2, minute=0),
            "kwargs": {"platform_take_rate": 0.20},
            "options": {"queue": "analytics"},
        },
        # NOTE: LoRA training cycle disabled - module not yet implemented
        # "lora-training-cycle": {
        #     "task": "kagami.lora.full_training_cycle",
        #     "schedule": crontab(day_of_week="sunday", hour=3, minute=0),
        #     "kwargs": {"lookback_days": 7, "auto_deploy": False, "rollout_pct": 0.2},
        #     "options": {"queue": "ml"},
        # },
        "sage-instinct-training": {
            "task": "kagami.core.tasks.processing_state.train_instincts_task",
            "schedule": 60.0,
            "options": {"queue": "ml"},
        },
        "lzc-monitor": {
            "task": "kagami.core.tasks.processing_state.update_lzc_task",
            "schedule": 30.0,
            "options": {"queue": "monitoring"},
        },
        "fractal-monitor": {
            "task": "kagami.core.tasks.processing_state.update_fractal_task",
            "schedule": 300.0,
            "options": {"queue": "monitoring"},
        },
        "synergy-monitor": {
            "task": "kagami.core.tasks.processing_state.update_synergy_task",
            "schedule": 600.0,
            "options": {"queue": "monitoring"},
        },
        "causal-monitor": {
            "task": "kagami.core.tasks.processing_state.update_causal_task",
            "schedule": 600.0,
            "options": {"queue": "monitoring"},
        },
        "autonomous-goals": {
            "task": "kagami.core.tasks.processing_state.generate_goals_task",
            "schedule": 300.0,
            "options": {"queue": "background"},
        },
        "composite-integration": {
            "task": "kagami.core.tasks.processing_state.compute_composite_integration",
            "schedule": 600.0,
            "options": {"queue": "monitoring"},
        },
        "gaussian-pid-synergy": {
            "task": "kagami.core.tasks.processing_state.gaussian_pid_synergy_task",
            "schedule": crontab(hour=3, minute=15),
            "options": {"queue": "ml"},
        },
        "slo-monitor": {
            "task": "kagami.core.tasks.tasks.slo_monitor_task",
            "schedule": 300.0,
            "options": {"queue": "monitoring"},
        },
        # Batch training (replaces internal coordinator loop)
        "batch-training": {
            "task": "kagami.core.tasks.processing_state.batch_train_task",
            "schedule": 300.0,  # Every 5 minutes
            "options": {"queue": "ml"},
        },
        # Evolution status monitoring (engine runs its own loop)
        "evolution-status": {
            "task": "kagami.core.tasks.processing_state.evolution_status_task",
            "schedule": 600.0,  # Every 10 minutes
            "options": {"queue": "monitoring"},
        },
        # Ambient services (periodic updates, not real-time)
        # NOTE: breath_engine runs at 30Hz in-process (not suitable for Celery)
        "context-tracker": {
            "task": "kagami.core.tasks.processing_state.context_tracker_task",
            "schedule": 60.0,  # Every minute
            "options": {"queue": "background"},
        },
        # NOTE: Notification delivery runs in-process at 1s (for UX responsiveness)
    }

    try:
        celery_app.autodiscover_tasks(["kagami.core.tasks"])
    except Exception:
        pass
