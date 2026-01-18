"""Integration tests for autonomous deployment system.

Tests the complete orchestration including:
- Self-modification with safety
- Colony coordination
- Monitoring metrics
- Graceful shutdown

Created: December 14, 2025
"""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


import asyncio
import time
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import torch

from kagami.core.executive.autonomous_orchestrator import (
    AutonomousOrchestrator,
    Intent,
    IntentQueue,
    OrchestrationMetrics,
)
from kagami.core.executive.monitoring_dashboard import (
    MetricWindow,
    MonitoringDashboard,
    SystemMetrics,
)
from kagami.core.executive.self_modification import (
    ModificationProposal,
    ModificationResult,
    ModificationType,
    SafetyStatus,
    SelfModificationEngine,
    SystemCheckpoint,
)


class TestSelfModification:
    """Test self-modification engine."""

    @pytest.fixture
    def safety_monitor(self):
        """Mock safety monitor."""
        monitor = MagicMock()
        monitor.get_status = AsyncMock(return_value=SafetyStatus.GREEN)
        return monitor

    @pytest.fixture
    def engine(self, safety_monitor: Any) -> Any:
        """Create self-modification engine."""
        return SelfModificationEngine(
            safety_monitor=safety_monitor,
            test_duration=0.1,  # Fast testing
            max_risk=0.5,
        )

    @pytest.mark.asyncio
    async def test_propose_modification(self, engine) -> Any:
        """Test modification proposal creation."""
        proposal = await engine.propose_modification(
            ModificationType.HYPERPARAMETER,
            "world_model",
            "learning_rate",
            proposed_value=1e-4,
            current_value=1e-3,
            rationale="Reduce for stability",
        )

        assert proposal.type == ModificationType.HYPERPARAMETER
        assert proposal.target_component == "world_model"
        assert proposal.parameter_name == "learning_rate"
        assert proposal.proposed_value == 1e-4
        assert proposal.risk_level >= 0.0
        assert proposal.risk_level <= 1.0

    @pytest.mark.asyncio
    async def test_safety_verification(self, engine) -> None:
        """Test safety verification of modifications."""
        # Low risk proposal should pass
        safe_proposal = ModificationProposal(
            type=ModificationType.HYPERPARAMETER,
            risk_level=0.2,
        )
        is_safe, reason = await engine.verify_safety(safe_proposal)
        assert is_safe is True

        # High risk proposal should fail
        risky_proposal = ModificationProposal(
            type=ModificationType.ARCHITECTURE,
            risk_level=0.8,
        )
        is_safe, reason = await engine.verify_safety(risky_proposal)
        assert is_safe is False
        assert "exceeds max" in reason

    @pytest.mark.asyncio
    async def test_apply_modification_success(self, engine) -> None:
        """Test successful modification application."""
        proposal = ModificationProposal(
            type=ModificationType.HYPERPARAMETER,
            target_component="test",
            parameter_name="value",
            current_value=1.0,
            proposed_value=2.0,
            risk_level=0.1,
        )

        # Mock target system
        target = MagicMock()
        target.value = 1.0

        result = await engine.apply_modification(proposal, target)

        assert result.success is True
        assert result.rollback_performed is False
        assert target.value == 2.0

    @pytest.mark.asyncio
    async def test_checkpoint_rollback(self, engine) -> None:
        """Test checkpoint and rollback functionality."""
        checkpoint = SystemCheckpoint("test_id")

        # Save state
        model = torch.nn.Linear(10, 10)
        original_weight = model.weight.data.clone()
        checkpoint.save_model("model", model)

        # Modify model
        model.weight.data.fill_(0)
        assert not torch.allclose(model.weight.data, original_weight)

        # Restore
        checkpoint.restore_model("model", model)
        assert torch.allclose(model.weight.data, original_weight)


class TestMonitoringDashboard:
    """Test monitoring dashboard."""

    @pytest.fixture
    def dashboard(self):
        """Create monitoring dashboard."""
        return MonitoringDashboard(
            export_prometheus=False,  # Disable for testing
            enable_wandb=False,
        )

    def test_metric_window(self) -> None:
        """Test metric window functionality."""
        window = MetricWindow(max_size=5)

        # Add values
        for i in range(10):
            window.add(float(i))

        # Should only keep last 5
        assert len(window.data) == 5
        assert list(window.data) == [5, 6, 7, 8, 9]
        assert window.mean() == 7.0

    def test_record_metrics(self, dashboard) -> None:
        """Test metric recording."""
        # Record receipts
        dashboard.record_receipt("spark", success=True, duration_ms=10)
        dashboard.record_receipt("forge", success=False, duration_ms=20)

        assert dashboard.metrics.receipts_by_colony["spark"] == 1
        assert dashboard.metrics.receipts_by_colony["forge"] == 1
        assert dashboard.metrics.receipt_success_rate.mean() == 0.5

        # Record learning
        dashboard.record_learning_step(loss=0.5, grad_norm=1.0)
        assert dashboard.metrics.loss_history.mean() == 0.5

        # Record safety
        dashboard.record_safety_status(safety_score=0.8, cbf_value=0.5)
        assert dashboard.metrics.safety_scores.mean() == 0.8

    def test_health_check(self, dashboard) -> None:
        """Test system health checking."""
        # Initially healthy
        is_healthy, issues = dashboard.check_health()
        assert is_healthy is True
        assert len(issues) == 0

        # Add safety violation
        dashboard.metrics.safety_violations = 5
        is_healthy, issues = dashboard.check_health()
        assert is_healthy is False
        assert any("Safety violations" in issue for issue in issues)

    def test_summary_export(self, dashboard) -> None:
        """Test metrics summary export."""
        # Add some data
        dashboard.record_receipt("spark", True, 10)
        dashboard.record_learning_step(0.5)
        dashboard.record_safety_status(0.9)

        summary = dashboard.get_summary()
        assert "total_receipts" in summary
        assert "average_loss" in summary
        assert "safety_score" in summary

        # Test JSON export
        json_str = dashboard.export_metrics_json()
        assert isinstance(json_str, str)
        assert "colonies" in json_str


class TestAutonomousOrchestrator:
    """Test autonomous orchestrator."""

    @pytest.fixture
    def orchestrator(self):
        """Create test orchestrator."""
        organism = MagicMock()
        organism.execute_intent = AsyncMock(return_value={"success": True})
        organism.get_state_embedding = AsyncMock(return_value=torch.randn(256))
        organism.shutdown = AsyncMock()

        safety_monitor = MagicMock()
        safety_monitor.get_status = AsyncMock(return_value=SafetyStatus.GREEN)

        return AutonomousOrchestrator(
            organism=organism,
            safety_monitor=safety_monitor,
            evolution_interval=1000.0,
            modification_interval=1000,
        )

    def test_intent_queue(self) -> None:
        """Test intent queue operations."""
        queue = IntentQueue()

        # Add intents with different priorities
        intent1 = Intent(type="low", priority=0.3)
        intent2 = Intent(type="high", priority=0.9)
        intent3 = Intent(type="medium", priority=0.5)

        queue.add(intent1)
        queue.add(intent2)
        queue.add(intent3)

        # Should get highest priority first
        asyncio.run(self._test_queue_order(queue, intent2, intent3, intent1))

    async def _test_queue_order(self, queue: Any, *expected_order: Any) -> None:
        """Helper to test queue ordering."""
        for expected in expected_order:
            intent = await queue.get_next()
            assert intent.id == expected.id

    @pytest.mark.asyncio
    async def test_execute_intent(self, orchestrator) -> None:
        """Test intent execution."""
        intent = Intent(
            type="test",
            description="Test intent",
            priority=0.5,
        )

        await orchestrator._execute_intent(intent)

        # Verify organism was called
        orchestrator.organism.execute_intent.assert_called_once()
        assert orchestrator.metrics.intents_processed == 1

    @pytest.mark.asyncio
    async def test_safety_monitoring(self, orchestrator) -> None:
        """Test safety monitoring triggers emergency stop."""
        # Set safety to RED
        orchestrator.safety_monitor.get_status = AsyncMock(return_value=SafetyStatus.RED)

        # Enable running flag so loop executes
        orchestrator.running = True

        # Run safety monitoring briefly
        task = asyncio.create_task(orchestrator._safety_monitoring_loop())
        await asyncio.sleep(0.1)
        task.cancel()

        assert orchestrator.emergency_stop_triggered is True
        assert orchestrator.metrics.safety_violations == 1

    @pytest.mark.asyncio
    async def test_convergence_tracking(self, orchestrator) -> None:
        """Test μ_self convergence tracking."""
        # Enable running flag so loop executes
        orchestrator.running = True

        # Run convergence tracking briefly
        task = asyncio.create_task(orchestrator._convergence_tracking_loop())
        await asyncio.sleep(0.1)
        task.cancel()

        # Should have recorded state
        assert len(orchestrator.mu_self_history) > 0
        assert orchestrator.metrics.mu_self_distance > 0

    @pytest.mark.asyncio
    async def test_graceful_shutdown(self, orchestrator, tmp_path) -> None:
        """Test graceful shutdown procedure."""
        orchestrator.checkpoint_dir = tmp_path

        await orchestrator.graceful_shutdown()

        # Should save checkpoint
        checkpoints = list(tmp_path.glob("shutdown_*.pt"))
        assert len(checkpoints) == 1

        # Load and verify checkpoint
        checkpoint = torch.load(checkpoints[0], weights_only=False)
        assert "metrics" in checkpoint
        assert "timestamp" in checkpoint

    @pytest.mark.asyncio
    async def test_full_orchestration_cycle(self, orchestrator) -> None:
        """Test a complete orchestration cycle."""
        # Add test intent
        await orchestrator.add_intent(
            "test",
            "Test orchestration",
            priority=0.8,
        )

        # Run one cycle
        orchestrator.running = True

        # Create a task to run the orchestrator
        task = asyncio.create_task(orchestrator.run_autonomously())

        # Let it run briefly
        await asyncio.sleep(0.2)

        # Stop it
        orchestrator.running = False
        task.cancel()

        # Verify execution
        assert orchestrator.metrics.step > 0
        assert orchestrator.metrics.intents_processed > 0


class TestIntegration:
    """Full integration tests."""

    @pytest.mark.asyncio
    async def test_end_to_end_deployment(self, tmp_path) -> None:
        """Test complete deployment cycle."""
        # Create all components
        organism = MagicMock()
        organism.execute_intent = AsyncMock(return_value={"success": True})
        organism.get_state_embedding = AsyncMock(return_value=torch.randn(256))
        organism.shutdown = AsyncMock()
        organism.get_status = AsyncMock(return_value={"healthy": True})

        safety_monitor = MagicMock()
        safety_monitor.get_status = AsyncMock(return_value=SafetyStatus.GREEN)

        self_modifier = SelfModificationEngine(
            safety_monitor=safety_monitor,
            test_duration=0.01,
        )

        dashboard = MonitoringDashboard(
            export_prometheus=False,
            enable_wandb=False,
        )

        orchestrator = AutonomousOrchestrator(
            organism=organism,
            safety_monitor=safety_monitor,
            self_modifier=self_modifier,
            checkpoint_dir=tmp_path,
            evolution_interval=1000.0,
            modification_interval=10,  # Quick for testing
        )

        # Add test intents
        for i in range(5):
            await orchestrator.add_intent(
                f"test_{i}",
                f"Test intent {i}",
                priority=0.5 + i * 0.1,
            )

        # Run briefly
        orchestrator.running = True
        task = asyncio.create_task(orchestrator.run_autonomously())
        await asyncio.sleep(0.5)

        # Graceful shutdown
        await orchestrator.graceful_shutdown()
        task.cancel()

        # Verify execution
        assert orchestrator.metrics.intents_processed > 0
        assert orchestrator.metrics.step > 0

        # Verify checkpoint saved
        checkpoints = list(tmp_path.glob("*.pt"))
        assert len(checkpoints) > 0

        # Get final status
        status = orchestrator.get_status()
        assert "metrics" in status
        assert status["emergency_stop"] is False
