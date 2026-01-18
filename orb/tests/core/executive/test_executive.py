"""Tests for Executive Control Module.

Tests configurator, task configuration, autonomous orchestrator,
self-modification engine, and monitoring dashboard.

CREATED: December 14, 2025
"""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration



import asyncio
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import numpy as np
import torch

from kagami.core.executive import (
    ConfiguratorConfig,
    ConfiguratorModule,
    IntegratedExecutiveControl,
    TaskConfiguration,
    PerceptionConfig,
    WorldModelConfig,
    CostConfig,
    ActorConfig,
    get_configurator,
    get_executive_control,
    reset_configurator,
)
from kagami.core.executive.autonomous_orchestrator import (
    AutonomousOrchestrator,
    Intent,
    IntentQueue,
    OrchestrationMetrics,
    OrchestrationPhase,
)
from kagami.core.executive.self_modification import (
    ModificationProposal,
    ModificationResult,
    ModificationType,
    SafetyMonitor,
    SafetyStatus,
    SelfModificationEngine,
    SystemCheckpoint,
)
from kagami.core.executive.monitoring_dashboard import (
    MonitoringDashboard,
    MetricWindow,
    SystemMetrics,
)

# =============================================================================
# TEST CONSTANTS
# =============================================================================

BATCH_SIZE = 4
TASK_DIM = 512
HIDDEN_DIM = 512
N_TOKENS = 4
TOKEN_DIM = 64

# =============================================================================
# CONFIGURATOR TESTS
# =============================================================================


class TestConfiguratorConfig:
    """Test ConfiguratorConfig dataclass."""

    def test_default_initialization(self):
        """Test default configuration values."""
        config = ConfiguratorConfig()
        assert config.task_dim == 512
        assert config.hidden_dim == 512
        assert config.n_heads == 8
        assert config.n_layers == 3
        assert config.dropout == 0.1
        assert len(config.task_types) == 8

    def test_custom_initialization(self):
        """Test custom configuration."""
        config = ConfiguratorConfig(
            hidden_dim=256,
            n_heads=4,
            n_layers=2,
        )
        assert config.hidden_dim == 256
        assert config.n_heads == 4
        assert config.n_layers == 2


class TestConfiguratorModule:
    """Test ConfiguratorModule neural network."""

    def test_initialization(self):
        """Test configurator module initialization."""
        config = ConfiguratorConfig(hidden_dim=256)
        configurator = ConfiguratorModule(config)

        assert configurator.config.hidden_dim == 256
        assert configurator.task_encoder is not None
        assert configurator.context_aggregator is not None

    def test_forward_pass(self):
        """Test forward pass with task embedding."""
        configurator = ConfiguratorModule()
        task_embedding = torch.randn(BATCH_SIZE, TASK_DIM)

        result = configurator.forward(task_embedding, task_type="general")

        # Check outputs exist
        assert "perception_config" in result
        assert "world_model_config" in result
        assert "cost_config" in result
        assert "actor_config" in result
        assert "urgency" in result
        assert "mode_logits" in result

        # Check shapes
        assert result["perception_config"].shape[0] == BATCH_SIZE
        assert result["perception_tokens"].shape == (BATCH_SIZE, N_TOKENS, TOKEN_DIM)
        assert result["urgency"].shape[0] == BATCH_SIZE

    def test_forward_with_module_states(self):
        """Test forward with module state inputs."""
        config = ConfiguratorConfig(
            perception_state_dim=128,
            world_model_state_dim=128,
            cost_state_dim=64,
            actor_state_dim=64,
        )
        configurator = ConfiguratorModule(config)

        task_embedding = torch.randn(BATCH_SIZE, TASK_DIM)
        perception_state = torch.randn(BATCH_SIZE, 128)
        world_model_state = torch.randn(BATCH_SIZE, 128)

        result = configurator.forward(
            task_embedding,
            perception_state=perception_state,
            world_model_state=world_model_state,
        )

        assert result["perception_config"].shape[0] == BATCH_SIZE

    def test_configure_method(self):
        """Test configure() method returns TaskConfiguration."""
        configurator = ConfiguratorModule()
        task_embedding = torch.randn(BATCH_SIZE, TASK_DIM)

        config = configurator.configure(task_embedding, task_type="planning")

        # Check returns TaskConfiguration
        assert isinstance(config, TaskConfiguration)
        assert config.task_type == "planning"
        assert isinstance(config.perception, PerceptionConfig)
        assert isinstance(config.world_model, WorldModelConfig)
        assert isinstance(config.cost, CostConfig)
        assert isinstance(config.actor, ActorConfig)
        assert 0.0 <= config.urgency <= 1.0

    def test_task_type_handling(self):
        """Test different task types."""
        configurator = ConfiguratorModule()
        task_embedding = torch.randn(BATCH_SIZE, TASK_DIM)

        task_types = ["general", "exploration", "planning", "safety_critical"]

        for task_type in task_types:
            config = configurator.configure(task_embedding, task_type=task_type)
            assert config.task_type == task_type

    def test_get_state(self):
        """Test get_state() method."""
        configurator = ConfiguratorModule()
        state = configurator.get_state()

        assert isinstance(state, torch.Tensor)
        assert state.shape[0] == 64


class TestIntegratedExecutiveControl:
    """Test IntegratedExecutiveControl integration."""

    def test_initialization(self):
        """Test executive control initialization."""
        executive = IntegratedExecutiveControl()

        assert executive._configurator is not None
        assert executive._reasoning_router is None  # Lazy loaded

    @pytest.mark.asyncio
    async def test_configure_for_task(self):
        """Test configure_for_task() method."""
        executive = IntegratedExecutiveControl()
        task_embedding = torch.randn(BATCH_SIZE, TASK_DIM)

        config = await executive.configure_for_task(
            task_embedding,
            task_type="exploration",
            task_description="Explore environment",
        )

        assert isinstance(config, TaskConfiguration)
        assert config.task_type == "exploration"

    @pytest.mark.asyncio
    async def test_configure_with_optional_routers(self):
        """Test configuration with optional routing systems."""
        executive = IntegratedExecutiveControl()
        task_embedding = torch.randn(BATCH_SIZE, TASK_DIM)

        # Should not fail if routing systems unavailable
        config = await executive.configure_for_task(
            task_embedding,
            task_description="Test task",
            time_budget=30.0,
        )

        assert config is not None

    def test_configurator_property(self):
        """Test configurator property access."""
        executive = IntegratedExecutiveControl()
        configurator = executive.configurator

        assert isinstance(configurator, ConfiguratorModule)


class TestSingletonAccessors:
    """Test singleton accessor functions."""

    def test_get_configurator(self):
        """Test get_configurator singleton."""
        reset_configurator()
        config1 = get_configurator()
        config2 = get_configurator()

        # Should return same instance
        assert config1 is config2

    def test_get_executive_control(self):
        """Test get_executive_control singleton."""
        reset_configurator()
        exec1 = get_executive_control()
        exec2 = get_executive_control()

        # Should return same instance
        assert exec1 is exec2

    def test_reset_configurator(self):
        """Test reset_configurator clears singletons."""
        exec1 = get_executive_control()
        reset_configurator()
        exec2 = get_executive_control()

        # Should be different instances after reset
        assert exec1 is not exec2


# =============================================================================
# TASK CONFIGURATION TESTS
# =============================================================================


class TestTaskConfiguration:
    """Test TaskConfiguration dataclass."""

    def test_default_initialization(self):
        """Test default task configuration."""
        config = TaskConfiguration()

        assert config.task_type == "general"
        assert isinstance(config.perception, PerceptionConfig)
        assert isinstance(config.world_model, WorldModelConfig)
        assert isinstance(config.cost, CostConfig)
        assert isinstance(config.actor, ActorConfig)
        assert config.urgency == 0.5

    def test_to_dict(self):
        """Test to_dict serialization."""
        config = TaskConfiguration(task_type="planning")
        config_dict = config.to_dict()

        assert config_dict["task_type"] == "planning"
        assert "perception" in config_dict
        assert "world_model" in config_dict
        assert "cost" in config_dict
        assert "actor" in config_dict

    def test_for_exploration(self):
        """Test exploration configuration factory."""
        config = TaskConfiguration.for_exploration()

        assert config.task_type == "exploration"
        assert config.cost.ic_weights["curiosity"] == 0.4
        assert config.cost.ic_weights["novelty"] == 0.3
        assert config.actor.exploration_rate == 0.3
        assert config.actor.mode == "mode_2"

    def test_for_exploitation(self):
        """Test exploitation configuration factory."""
        config = TaskConfiguration.for_exploitation()

        assert config.task_type == "exploitation"
        assert config.cost.tc_weights["task_progress"] == 0.6
        assert config.actor.exploration_rate == 0.05
        assert config.actor.mode == "mode_1"
        assert config.actor.use_compiled_skill is True

    def test_for_safety_critical(self):
        """Test safety-critical configuration factory."""
        config = TaskConfiguration.for_safety_critical()

        assert config.task_type == "safety_critical"
        assert config.cost.ic_weights["safety"] == 0.6
        assert config.cost.risk_sensitivity == 0.5
        assert config.actor.mode == "mode_2"
        assert config.world_model.uncertainty_mode == "ensemble"
        assert config.precision_mode is True

    def test_for_hierarchical_planning(self):
        """Test hierarchical planning configuration factory."""
        config = TaskConfiguration.for_hierarchical_planning()

        assert config.task_type == "hierarchical"
        assert config.actor.mode == "hierarchical"
        assert config.actor.hierarchy_levels == 3
        assert config.world_model.horizon == 100


class TestPerceptionConfig:
    """Test PerceptionConfig."""

    def test_default_initialization(self):
        """Test default perception config."""
        config = PerceptionConfig()

        assert config.mode == "standard"
        assert config.temporal_context == 8
        assert config.modality_weights["vision"] == 1.0


class TestWorldModelConfig:
    """Test WorldModelConfig."""

    def test_default_initialization(self):
        """Test default world model config."""
        config = WorldModelConfig()

        assert config.horizon == 10
        assert config.abstraction_level == 0
        assert config.e8_levels == 4
        assert config.uncertainty_mode == "stochastic"


class TestCostConfig:
    """Test CostConfig."""

    def test_default_initialization(self):
        """Test default cost config."""
        config = CostConfig()

        assert config.ic_weights["safety"] == 0.3
        assert config.tc_weights["task_progress"] == 0.4
        assert config.discount == 0.99


class TestActorConfig:
    """Test ActorConfig."""

    def test_default_initialization(self):
        """Test default actor config."""
        config = ActorConfig()

        assert config.mode == "mode_2"
        assert config.planning_horizon == 10
        assert config.exploration_rate == 0.1


# =============================================================================
# AUTONOMOUS ORCHESTRATOR TESTS
# =============================================================================


class TestIntent:
    """Test Intent dataclass."""

    def test_default_initialization(self):
        """Test default intent creation."""
        intent = Intent(type="test", description="Test intent")

        assert intent.type == "test"
        assert intent.description == "Test intent"
        assert intent.priority == 0.5
        assert intent.id is not None


class TestIntentQueue:
    """Test IntentQueue."""

    @pytest.mark.asyncio
    async def test_add_and_get(self):
        """Test adding and retrieving intents."""
        queue = IntentQueue()
        intent = Intent(type="test", priority=0.8)
        queue.add(intent)

        retrieved = await queue.get_next()
        assert retrieved == intent

    @pytest.mark.asyncio
    async def test_priority_ordering(self):
        """Test that higher priority intents come first."""
        queue = IntentQueue()
        low = Intent(type="low", priority=0.3)
        high = Intent(type="high", priority=0.9)
        queue.add(low)
        queue.add(high)

        first = await queue.get_next()
        assert first == high

    @pytest.mark.asyncio
    async def test_empty_queue_returns_default(self):
        """Test empty queue returns exploration intent."""
        queue = IntentQueue()
        intent = await queue.get_next()

        assert intent is not None
        assert intent.type == "explore"


class TestOrchestrationMetrics:
    """Test OrchestrationMetrics."""

    def test_default_initialization(self):
        """Test default metrics."""
        metrics = OrchestrationMetrics()

        assert metrics.step == 0
        assert metrics.intents_processed == 0
        assert metrics.safety_violations == 0
        assert metrics.population_size == 7


class TestAutonomousOrchestrator:
    """Test AutonomousOrchestrator."""

    def test_initialization(self):
        """Test orchestrator initialization."""
        orchestrator = AutonomousOrchestrator()

        assert orchestrator.metrics is not None
        assert orchestrator.intent_queue is not None
        assert orchestrator.running is False
        assert orchestrator.safety_monitor is not None

    def test_initialization_with_custom_intervals(self):
        """Test custom interval configuration."""
        orchestrator = AutonomousOrchestrator(
            evolution_interval=1800.0,
            modification_interval=1000.0,
        )

        assert orchestrator.evolution_interval == 1800.0
        assert orchestrator.modification_interval == 1000.0

    @pytest.mark.asyncio
    async def test_add_intent(self):
        """Test adding intent to queue."""
        orchestrator = AutonomousOrchestrator()

        await orchestrator.add_intent(
            "test_task",
            "Test description",
            priority=0.7,
        )

        assert len(orchestrator.intent_queue.queue) == 1

    @pytest.mark.asyncio
    async def test_execute_intent(self):
        """Test intent execution (mocked)."""
        # Create orchestrator with mocked organism
        mock_organism = Mock()
        mock_organism.execute_intent = AsyncMock(return_value={"success": True})

        orchestrator = AutonomousOrchestrator(organism=mock_organism)
        intent = Intent(type="test", description="Test")

        await orchestrator._execute_intent(intent)

        # Verify organism was called
        mock_organism.execute_intent.assert_called_once()
        assert orchestrator.metrics.intents_processed == 1

    def test_should_evolve(self):
        """Test evolution timing logic."""
        orchestrator = AutonomousOrchestrator(
            population=Mock(),
            evolution_interval=1.0,
        )

        # Should not evolve immediately
        assert not orchestrator._should_evolve()

        # Should evolve after interval
        orchestrator.metrics.last_evolution = time.time() - 2.0
        assert orchestrator._should_evolve()

    def test_should_modify(self):
        """Test modification timing logic."""
        orchestrator = AutonomousOrchestrator(
            self_modifier=Mock(),
            modification_interval=10,
        )

        # Should not modify at step 0
        orchestrator.metrics.step = 0
        assert not orchestrator._should_modify()

        # Should modify at interval
        orchestrator.metrics.step = 10
        assert orchestrator._should_modify()

    @pytest.mark.asyncio
    async def test_emergency_stop(self):
        """Test emergency stop mechanism."""
        orchestrator = AutonomousOrchestrator()
        orchestrator.organism = Mock()
        orchestrator.organism.shutdown = AsyncMock()

        await orchestrator.emergency_stop()

        assert orchestrator.emergency_stop_triggered is True
        assert orchestrator.running is False
        orchestrator.organism.shutdown.assert_called_once()

    def test_get_status(self):
        """Test status reporting."""
        orchestrator = AutonomousOrchestrator()
        orchestrator.metrics.intents_processed = 42

        status = orchestrator.get_status()

        assert status["running"] is False
        assert status["metrics"]["intents_processed"] == 42
        assert "queue_size" in status


# =============================================================================
# SELF-MODIFICATION ENGINE TESTS
# =============================================================================


class TestSafetyMonitor:
    """Test SafetyMonitor."""

    @pytest.mark.asyncio
    async def test_get_status(self):
        """Test getting safety status."""
        monitor = SafetyMonitor()
        status = await monitor.get_status()

        assert status in [SafetyStatus.GREEN, SafetyStatus.YELLOW, SafetyStatus.RED]


class TestModificationProposal:
    """Test ModificationProposal."""

    def test_initialization(self):
        """Test proposal creation."""
        proposal = ModificationProposal(
            type=ModificationType.HYPERPARAMETER,
            target_component="world_model",
            parameter_name="learning_rate",
            current_value=1e-3,
            proposed_value=5e-4,
            rationale="Reduce for stability",
        )

        assert proposal.type == ModificationType.HYPERPARAMETER
        assert proposal.parameter_name == "learning_rate"
        assert proposal.id is not None

    def test_to_dict(self):
        """Test proposal serialization."""
        proposal = ModificationProposal(
            type=ModificationType.ARCHITECTURE,
            target_component="encoder",
            parameter_name="hidden_dim",
        )

        data = proposal.to_dict()
        assert data["type"] == "architecture"
        assert data["target"] == "encoder"


class TestSystemCheckpoint:
    """Test SystemCheckpoint."""

    def test_initialization(self):
        """Test checkpoint creation."""
        checkpoint = SystemCheckpoint("test_checkpoint")

        assert checkpoint.id == "test_checkpoint"
        assert isinstance(checkpoint.timestamp, float)

    def test_save_and_restore_model(self):
        """Test model state save/restore."""
        checkpoint = SystemCheckpoint("test")
        model = torch.nn.Linear(10, 5)

        checkpoint.save_model("test_model", model)
        assert "test_model" in checkpoint.state_dicts

        # Modify model
        with torch.no_grad():
            model.weight.fill_(0.0)

        # Restore
        checkpoint.restore_model("test_model", model)
        # Should be restored (not all zeros)
        assert not torch.allclose(model.weight, torch.zeros_like(model.weight))

    def test_save_and_get_param(self):
        """Test parameter save/get."""
        checkpoint = SystemCheckpoint("test")
        checkpoint.save_param("learning_rate", 0.001)

        value = checkpoint.get_param("learning_rate")
        assert value == 0.001


class TestSelfModificationEngine:
    """Test SelfModificationEngine."""

    def test_initialization(self):
        """Test engine initialization."""
        safety_monitor = SafetyMonitor()
        engine = SelfModificationEngine(
            safety_monitor=safety_monitor,
            max_risk=0.4,
        )

        assert engine.safety_monitor is not None
        assert engine.max_risk == 0.4
        assert len(engine.modification_history) == 0

    @pytest.mark.asyncio
    async def test_propose_modification(self):
        """Test modification proposal."""
        engine = SelfModificationEngine(SafetyMonitor())

        proposal = await engine.propose_modification(
            ModificationType.HYPERPARAMETER,
            "world_model",
            "learning_rate",
            proposed_value=5e-4,
            current_value=1e-3,
            rationale="Improve stability",
        )

        assert proposal.type == ModificationType.HYPERPARAMETER
        assert proposal.parameter_name == "learning_rate"
        assert 0.0 <= proposal.risk_level <= 1.0

    @pytest.mark.asyncio
    async def test_verify_safety_accepts_low_risk(self):
        """Test safety verification accepts low-risk changes."""
        engine = SelfModificationEngine(SafetyMonitor(), max_risk=0.5)

        proposal = ModificationProposal(
            type=ModificationType.HYPERPARAMETER,
            target_component="test",
            parameter_name="test_param",
            risk_level=0.2,
        )

        is_safe, _reason = await engine.verify_safety(proposal)
        assert is_safe

    @pytest.mark.asyncio
    async def test_verify_safety_rejects_high_risk(self):
        """Test safety verification rejects high-risk changes."""
        engine = SelfModificationEngine(SafetyMonitor(), max_risk=0.3)

        proposal = ModificationProposal(
            type=ModificationType.ARCHITECTURE,
            target_component="test",
            parameter_name="test_param",
            risk_level=0.8,
        )

        is_safe, reason = await engine.verify_safety(proposal)
        assert not is_safe
        assert "exceeds max" in reason

    @pytest.mark.asyncio
    async def test_verify_safety_rejects_safety_margin_reduction(self):
        """Test that safety margin reductions are rejected."""
        engine = SelfModificationEngine(SafetyMonitor())

        proposal = ModificationProposal(
            type=ModificationType.SAFETY_MARGIN,
            target_component="cbf",
            parameter_name="threshold",
            current_value=0.1,
            proposed_value=0.05,  # Reduction
            risk_level=0.2,
        )

        is_safe, reason = await engine.verify_safety(proposal)
        assert not is_safe
        assert "Cannot reduce safety margins" in reason

    @pytest.mark.asyncio
    async def test_propose_improvement_cycle(self):
        """Test improvement proposal generation."""
        engine = SelfModificationEngine(SafetyMonitor())

        proposals = await engine.propose_improvement_cycle()

        assert isinstance(proposals, list)
        # Should generate at least one proposal
        assert len(proposals) >= 1
        assert all(isinstance(p, ModificationProposal) for p in proposals)

    def test_get_modification_stats(self):
        """Test modification statistics."""
        engine = SelfModificationEngine(SafetyMonitor())

        # No history
        stats = engine.get_modification_stats()
        assert stats["total_modifications"] == 0
        assert stats["successful"] == 0

        # Add some results
        engine.modification_history.append(
            ModificationResult(
                proposal_id="test1",
                success=True,
                actual_improvement=0.05,
            )
        )
        engine.modification_history.append(
            ModificationResult(
                proposal_id="test2",
                success=False,
                rollback_performed=True,
            )
        )

        stats = engine.get_modification_stats()
        assert stats["total_modifications"] == 2
        assert stats["successful"] == 1
        assert stats["rolled_back"] == 1


# =============================================================================
# MONITORING DASHBOARD TESTS
# =============================================================================


class TestMetricWindow:
    """Test MetricWindow."""

    def test_initialization(self):
        """Test window initialization."""
        window = MetricWindow(max_size=100)
        assert len(window.data) == 0
        assert window.max_size == 100

    def test_add_values(self):
        """Test adding values."""
        window = MetricWindow(max_size=5)

        for i in range(10):
            window.add(float(i))

        assert len(window.data) == 5
        assert window.data[-1] == 9.0

    def test_get_recent(self):
        """Test getting recent values."""
        window = MetricWindow()

        # Add values with timestamps
        now = time.time()
        window.add(1.0, now - 100)
        window.add(2.0, now - 50)
        window.add(3.0, now - 10)

        recent = window.get_recent(60.0)
        assert len(recent) == 2  # Last two are within 60 seconds

    def test_mean(self):
        """Test mean calculation."""
        window = MetricWindow()
        window.add(1.0)
        window.add(2.0)
        window.add(3.0)

        assert window.mean() == 2.0

    def test_std(self):
        """Test standard deviation."""
        window = MetricWindow()
        window.add(1.0)
        window.add(2.0)
        window.add(3.0)

        std = window.std()
        assert std > 0


class TestSystemMetrics:
    """Test SystemMetrics."""

    def test_initialization(self):
        """Test metrics initialization."""
        metrics = SystemMetrics()

        assert isinstance(metrics.loss_history, MetricWindow)
        assert metrics.safety_violations == 0
        assert metrics.population_size == 7


class TestMonitoringDashboard:
    """Test MonitoringDashboard."""

    def test_initialization(self):
        """Test dashboard initialization."""
        dashboard = MonitoringDashboard(
            export_prometheus=False,
            enable_wandb=False,
        )

        assert dashboard.metrics is not None
        assert dashboard.export_prometheus is False

    def test_record_receipt(self):
        """Test receipt recording."""
        dashboard = MonitoringDashboard(export_prometheus=False)

        dashboard.record_receipt("spark", True, 123.4)

        assert dashboard.metrics.receipts_by_colony["spark"] == 1

    def test_record_learning_step(self):
        """Test learning metrics recording."""
        dashboard = MonitoringDashboard(export_prometheus=False)

        dashboard.record_learning_step(0.5, grad_norm=1.2)

        assert len(dashboard.metrics.loss_history.data) == 1
        assert dashboard.metrics.loss_history.data[0] == 0.5

    def test_record_safety_status(self):
        """Test safety status recording."""
        dashboard = MonitoringDashboard(export_prometheus=False)

        dashboard.record_safety_status(0.3, cbf_value=0.2)

        assert dashboard.metrics.safety_violations == 1
        assert len(dashboard.metrics.safety_scores.data) == 1

    def test_record_colony_activity(self):
        """Test colony activity recording."""
        dashboard = MonitoringDashboard(export_prometheus=False)

        dashboard.record_colony_activity("forge", 45.6)

        assert dashboard.metrics.colony_calls["forge"] == 1

    def test_record_mu_self_convergence(self):
        """Test μ_self convergence tracking."""
        dashboard = MonitoringDashboard(export_prometheus=False)

        dashboard.record_mu_self_convergence(0.5)
        dashboard.record_mu_self_convergence(0.4)

        assert len(dashboard.metrics.mu_self_trajectory) == 2

    def test_record_population_metrics(self):
        """Test population metrics recording."""
        dashboard = MonitoringDashboard(export_prometheus=False)

        dashboard.record_population_metrics(
            population_size=10,
            best_fitness=0.85,
            diversity=0.6,
        )

        assert dashboard.metrics.population_size == 10
        assert dashboard.metrics.best_fitness == 0.85

    def test_record_modification(self):
        """Test modification recording."""
        dashboard = MonitoringDashboard(export_prometheus=False)

        dashboard.record_modification(success=True, improvement=0.05)

        # Should not raise errors

    def test_get_summary(self):
        """Test summary generation."""
        dashboard = MonitoringDashboard(export_prometheus=False)

        # Record some data
        dashboard.record_receipt("spark", True, 100.0)
        dashboard.record_learning_step(0.5)
        dashboard.record_safety_status(0.8)

        summary = dashboard.get_summary()

        assert "uptime_hours" in summary
        assert summary["total_receipts"] == 1
        assert summary["average_loss"] == 0.5

    def test_export_metrics_json(self):
        """Test JSON export."""
        dashboard = MonitoringDashboard(export_prometheus=False)

        dashboard.record_receipt("spark", True, 100.0)

        json_str = dashboard.export_metrics_json()
        assert isinstance(json_str, str)
        assert "total_receipts" in json_str

    def test_check_health(self):
        """Test health checking."""
        dashboard = MonitoringDashboard(export_prometheus=False)

        is_healthy, issues = dashboard.check_health()

        # Should be healthy initially
        assert is_healthy
        assert len(issues) == 0

        # Add safety violation
        dashboard.metrics.safety_violations = 1
        is_healthy, issues = dashboard.check_health()
        assert not is_healthy
        assert len(issues) > 0

    def test_generate_alert(self):
        """Test alert generation."""
        dashboard = MonitoringDashboard(export_prometheus=False)

        alert = dashboard.generate_alert("Test condition", severity="warning")

        assert alert["severity"] == "warning"
        assert alert["condition"] == "Test condition"
        assert "metrics" in alert


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestExecutiveIntegration:
    """Integration tests across executive components."""

    @pytest.mark.asyncio
    async def test_configurator_to_task_configuration(self):
        """Test full pipeline from configurator to task config."""
        configurator = ConfiguratorModule()
        task_embedding = torch.randn(1, TASK_DIM)

        # Generate configuration
        config = configurator.configure(task_embedding, task_type="exploration")

        # Verify complete configuration
        assert isinstance(config, TaskConfiguration)
        assert config.task_type == "exploration"
        assert config.world_model.horizon > 0
        assert 0.0 <= config.urgency <= 1.0

    @pytest.mark.asyncio
    async def test_executive_control_end_to_end(self):
        """Test executive control from task to configuration."""
        reset_configurator()
        executive = get_executive_control()

        task_embedding = torch.randn(1, TASK_DIM)
        config = await executive.configure_for_task(
            task_embedding,
            task_type="safety_critical",
            task_description="Critical system operation",
        )

        assert config.task_type == "safety_critical"

    @pytest.mark.asyncio
    async def test_orchestrator_with_monitoring(self):
        """Test orchestrator with monitoring dashboard."""
        dashboard = MonitoringDashboard(export_prometheus=False)

        # Create orchestrator with mocked components
        mock_organism = Mock()
        mock_organism.execute_intent = AsyncMock(return_value={"success": True})

        orchestrator = AutonomousOrchestrator(organism=mock_organism)

        # Add and execute intent
        await orchestrator.add_intent("test", "Test task", priority=0.5)

        intent = await orchestrator.intent_queue.get_next()
        await orchestrator._execute_intent(intent)  # type: ignore[arg-type]

        # Record to dashboard
        dashboard.record_receipt("test", True, 100.0)

        # Verify
        assert orchestrator.metrics.intents_processed == 1
        assert dashboard.metrics.receipts_by_colony["test"] == 1
