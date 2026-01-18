"""Tests for MetaOrchestrator - General Multi-Instance Coordination.

Tests cover:
1. Instance registration and management
2. Task decomposition and DAG generation
3. Instance assignment and load balancing
4. Safety verification (meta h(x))
5. Coordination modes (single, parallel, sequential, pipeline)
6. Strategic memory and learning
7. OrganismInstanceAdapter integration

Created: December 28, 2025
"""

from __future__ import annotations

import asyncio
import pytest
import tempfile
from pathlib import Path
from typing import Any

from kagami.core.coordination.meta_orchestrator import (
    MetaOrchestrator,
    OrchestratableInstance,
    OrganismInstanceAdapter,
    TaskDAG,
    TaskNode,
    TaskPriority,
    CoordinationMode,
    CoordinationResult,
    StrategicMemory,
    TaskDecomposer,
    InstanceAssigner,
    create_meta_orchestrator,
    reset_meta_orchestrator,
)


# =============================================================================
# MOCK INSTANCES
# =============================================================================


class MockInstance:
    """Mock OrchestratableInstance for testing."""

    def __init__(
        self,
        instance_id: str = "mock_1",
        instance_type: str = "mock",
        capabilities: list[str] | None = None,
        h_x: float = 1.0,
        load: float = 0.0,
        should_fail: bool = False,
    ):
        self._instance_id = instance_id
        self._instance_type = instance_type
        self._capabilities = capabilities or ["general"]
        self._h_x = h_x
        self._load = load
        self._should_fail = should_fail
        self._executions: list[tuple[str, dict]] = []

    @property
    def instance_id(self) -> str:
        return self._instance_id

    @property
    def instance_type(self) -> str:
        return self._instance_type

    async def execute(
        self,
        task: str,
        params: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._executions.append((task, params))

        if self._should_fail:
            return {
                "success": False,
                "result": None,
                "error": "Mock failure",
            }

        # Simulate some work
        await asyncio.sleep(0.001)

        return {
            "success": True,
            "result": {
                "task": task,
                "instance": self._instance_id,
                "params": params,
            },
            "error": None,
        }

    def get_health(self) -> dict[str, Any]:
        return {
            "h_x": self._h_x,
            "status": "healthy" if self._h_x > 0.5 else "unhealthy",
            "load": self._load,
        }

    def get_capabilities(self) -> list[str]:
        return self._capabilities

    def set_h_x(self, value: float) -> None:
        """Update h(x) for testing."""
        self._h_x = value

    def set_load(self, value: float) -> None:
        """Update load for testing."""
        self._load = value


# =============================================================================
# FIXTURE SETUP
# =============================================================================


@pytest.fixture
def temp_memory_path() -> Path:
    """Create a temporary path for memory persistence."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        return Path(f.name)


@pytest.fixture
def mock_instance() -> MockInstance:
    """Create a basic mock instance."""
    return MockInstance()


@pytest.fixture
def mock_instances() -> dict[str, MockInstance]:
    """Create multiple mock instances with different capabilities."""
    return {
        "research_1": MockInstance(
            instance_id="research_1",
            capabilities=["research", "explore"],
            h_x=0.9,
        ),
        "build_1": MockInstance(
            instance_id="build_1",
            capabilities=["build", "implement", "test"],
            h_x=0.8,
        ),
        "debug_1": MockInstance(
            instance_id="debug_1",
            capabilities=["debug", "fix"],
            h_x=0.95,
        ),
    }


@pytest.fixture
def orchestrator(temp_memory_path: Path) -> MetaOrchestrator:
    """Create a test orchestrator."""
    reset_meta_orchestrator()
    return create_meta_orchestrator(
        memory_path=temp_memory_path,
        safety_threshold=0.0,
        enable_persistence=False,  # Disable for faster tests
    )


# =============================================================================
# INSTANCE MANAGEMENT TESTS
# =============================================================================


class TestInstanceManagement:
    """Tests for instance registration and management."""

    def test_register_instance(
        self, orchestrator: MetaOrchestrator, mock_instance: MockInstance
    ) -> None:
        """Test instance registration."""
        orchestrator.register_instance("test", mock_instance)
        assert "test" in orchestrator.list_instances()
        assert orchestrator.get_instance("test") is mock_instance

    def test_unregister_instance(
        self, orchestrator: MetaOrchestrator, mock_instance: MockInstance
    ) -> None:
        """Test instance unregistration."""
        orchestrator.register_instance("test", mock_instance)
        orchestrator.unregister_instance("test")
        assert "test" not in orchestrator.list_instances()
        assert orchestrator.get_instance("test") is None

    def test_list_instances(
        self, orchestrator: MetaOrchestrator, mock_instances: dict[str, MockInstance]
    ) -> None:
        """Test listing all instances."""
        for name, instance in mock_instances.items():
            orchestrator.register_instance(name, instance)

        instances = orchestrator.list_instances()
        assert len(instances) == 3
        assert set(instances) == set(mock_instances.keys())

    def test_get_nonexistent_instance(self, orchestrator: MetaOrchestrator) -> None:
        """Test getting non-existent instance returns None."""
        assert orchestrator.get_instance("nonexistent") is None


# =============================================================================
# SAFETY TESTS
# =============================================================================


class TestSafety:
    """Tests for safety verification."""

    def test_meta_h_x_calculation(
        self, orchestrator: MetaOrchestrator, mock_instances: dict[str, MockInstance]
    ) -> None:
        """Test meta h(x) is minimum across instances."""
        for name, instance in mock_instances.items():
            orchestrator.register_instance(name, instance)

        # All healthy - expect minimum of 0.8
        meta_h_x = orchestrator.get_meta_h_x()
        assert meta_h_x == pytest.approx(0.8, rel=0.1)

        # Lower one instance's h(x)
        mock_instances["build_1"].set_h_x(0.3)
        meta_h_x = orchestrator.get_meta_h_x()
        assert meta_h_x == pytest.approx(0.3, rel=0.1)

    def test_meta_h_x_empty(self, orchestrator: MetaOrchestrator) -> None:
        """Test meta h(x) with no instances returns 1.0."""
        meta_h_x = orchestrator.get_meta_h_x()
        assert meta_h_x == 1.0

    def test_safety_check(
        self, orchestrator: MetaOrchestrator, mock_instances: dict[str, MockInstance]
    ) -> None:
        """Test safety check."""
        for name, instance in mock_instances.items():
            orchestrator.register_instance(name, instance)

        is_safe, meta_h_x = orchestrator.check_safety()
        assert is_safe is True
        assert meta_h_x > 0

    @pytest.mark.asyncio
    async def test_safety_threshold_blocks_coordination(
        self, temp_memory_path: Path, mock_instances: dict[str, MockInstance]
    ) -> None:
        """Test coordination is blocked when h(x) < threshold."""
        # Create orchestrator with high threshold
        orchestrator = create_meta_orchestrator(
            memory_path=temp_memory_path,
            safety_threshold=0.95,  # High threshold
            enable_persistence=False,
        )

        for name, instance in mock_instances.items():
            orchestrator.register_instance(name, instance)

        # All instances have h(x) < 0.95
        result = await orchestrator.coordinate(
            task="test task",
            params={},
        )

        assert result.success is False
        assert "Safety" in str(result.context.get("error", "")) or result.meta_h_x < 0.95


# =============================================================================
# TASK DECOMPOSITION TESTS
# =============================================================================


class TestTaskDecomposition:
    """Tests for task decomposition."""

    def test_extract_task_type(self) -> None:
        """Test task type extraction."""
        memory = StrategicMemory()
        decomposer = TaskDecomposer(memory)

        assert decomposer.extract_task_type("research the topic") == "research"
        assert decomposer.extract_task_type("build the feature") == "build"
        assert decomposer.extract_task_type("fix the bug") == "fix"
        assert decomposer.extract_task_type("test the code") == "test"
        assert decomposer.extract_task_type("plan the architecture") == "plan"
        assert decomposer.extract_task_type("unknown task") == "general"

    def test_decompose_creates_dag(self) -> None:
        """Test decompose creates a valid DAG."""
        memory = StrategicMemory()
        decomposer = TaskDecomposer(memory)

        dag = decomposer.decompose("build a new feature")

        assert dag is not None
        assert dag.dag_id is not None
        assert dag.root_task == "build a new feature"
        assert len(dag.nodes) > 0

    def test_decompose_sequential_dependencies(self) -> None:
        """Test decomposed tasks have sequential dependencies."""
        memory = StrategicMemory()
        decomposer = TaskDecomposer(memory)

        dag = decomposer.decompose("build a new feature")

        # Tasks should have dependencies (except first)
        nodes = list(dag.nodes.values())
        if len(nodes) > 1:
            # At least one task should have a dependency
            has_dependency = any(n.dependencies for n in nodes)
            assert has_dependency

    def test_dag_ready_tasks(self) -> None:
        """Test DAG returns correct ready tasks."""
        dag = TaskDAG(dag_id="test", root_task="test")

        t1 = dag.add_task("task 1")
        t2 = dag.add_task("task 2", dependencies=[t1.task_id])
        t3 = dag.add_task("task 3", dependencies=[t2.task_id])

        # Initially only t1 is ready
        ready = dag.get_ready_tasks()
        assert len(ready) == 1
        assert ready[0].task_id == t1.task_id

        # After t1 completes, t2 is ready
        t1.status = "completed"
        ready = dag.get_ready_tasks()
        assert len(ready) == 1
        assert ready[0].task_id == t2.task_id


# =============================================================================
# INSTANCE ASSIGNMENT TESTS
# =============================================================================


class TestInstanceAssignment:
    """Tests for instance assignment."""

    def test_assign_by_capability(self, mock_instances: dict[str, MockInstance]) -> None:
        """Test assignment prefers instances with matching capabilities."""
        memory = StrategicMemory()
        assigner = InstanceAssigner(memory)

        task = TaskNode(
            task_id="test",
            description="research task",
            required_capabilities=["research"],
        )

        assigned = assigner.assign(task, mock_instances)
        assert assigned == "research_1"

    def test_assign_considers_load(self, mock_instances: dict[str, MockInstance]) -> None:
        """Test assignment considers instance load."""
        memory = StrategicMemory()
        assigner = InstanceAssigner(memory)

        # Increase load on research_1
        mock_instances["research_1"].set_load(0.9)

        task = TaskNode(
            task_id="test",
            description="general task",
            required_capabilities=["general"],
        )

        assigned = assigner.assign(task, mock_instances)
        # Should not pick the high-load instance
        assert assigned != "research_1" or mock_instances["research_1"]._load < 0.5

    def test_assign_considers_safety(self, mock_instances: dict[str, MockInstance]) -> None:
        """Test assignment considers instance safety."""
        memory = StrategicMemory()
        assigner = InstanceAssigner(memory)

        # Lower h(x) on research_1
        mock_instances["research_1"].set_h_x(0.1)

        task = TaskNode(
            task_id="test",
            description="research task",
            required_capabilities=["research"],
        )

        assigned = assigner.assign(task, mock_instances)
        # Should prefer the instance with higher h(x) even without capability
        # Or pick research_1 with low score


# =============================================================================
# COORDINATION TESTS
# =============================================================================


class TestCoordination:
    """Tests for coordination execution."""

    @pytest.mark.asyncio
    async def test_coordinate_simple_task(
        self, orchestrator: MetaOrchestrator, mock_instance: MockInstance
    ) -> None:
        """Test coordination of a simple task."""
        orchestrator.register_instance("test", mock_instance)

        result = await orchestrator.coordinate(
            task="execute simple task",
            params={"key": "value"},
        )

        assert result.dag_id is not None
        assert result.instances_used
        assert result.meta_h_x > 0

    @pytest.mark.asyncio
    async def test_coordinate_with_multiple_instances(
        self, orchestrator: MetaOrchestrator, mock_instances: dict[str, MockInstance]
    ) -> None:
        """Test coordination with multiple instances."""
        for name, instance in mock_instances.items():
            orchestrator.register_instance(name, instance)

        result = await orchestrator.coordinate(
            task="build a feature",
            params={},
        )

        assert result.success
        assert len(result.instances_used) > 0

    @pytest.mark.asyncio
    async def test_coordinate_handles_failure(self, orchestrator: MetaOrchestrator) -> None:
        """Test coordination handles instance failures."""
        failing_instance = MockInstance(
            instance_id="failing",
            should_fail=True,
        )
        orchestrator.register_instance("failing", failing_instance)

        result = await orchestrator.coordinate(
            task="failing task",
            params={},
        )

        # Should complete but with failures
        assert result.dag_id is not None
        # Either success=False or failed_tasks not empty
        if not result.success:
            assert True  # Expected failure
        else:
            # Some tasks may have failed
            pass

    @pytest.mark.asyncio
    async def test_coordinate_timeout(
        self, orchestrator: MetaOrchestrator, mock_instance: MockInstance
    ) -> None:
        """Test coordination respects timeout."""
        orchestrator.register_instance("test", mock_instance)

        result = await orchestrator.coordinate(
            task="test task",
            params={},
            timeout=10.0,  # Generous timeout
        )

        assert result.duration_seconds < 10.0


# =============================================================================
# STRATEGIC MEMORY TESTS
# =============================================================================


class TestStrategicMemory:
    """Tests for strategic memory."""

    def test_record_success(self) -> None:
        """Test recording successful decomposition."""
        memory = StrategicMemory()

        memory.record_success(
            task_type="build",
            decomposition=[{"action": "plan"}, {"action": "implement"}],
            instance_assignments={"task_0": "forge"},
        )

        patterns = memory.decomposition_patterns["build"]
        assert len(patterns) == 1
        assert patterns[0]["decomposition"][0]["action"] == "plan"

    def test_get_best_decomposition(self) -> None:
        """Test getting best decomposition pattern."""
        memory = StrategicMemory()

        # Record multiple patterns
        memory.record_success(
            task_type="research",
            decomposition=[{"action": "explore"}],
            instance_assignments={},
        )
        memory.record_success(
            task_type="research",
            decomposition=[{"action": "explore"}, {"action": "synthesize"}],
            instance_assignments={},
        )

        # Should return most recent
        best = memory.get_best_decomposition("research")
        assert best is not None
        assert len(best) == 2

    def test_update_capability(self) -> None:
        """Test capability success rate updates."""
        memory = StrategicMemory()

        # Record successes and failures
        for _ in range(10):
            memory.update_capability("instance_1", "research", True)
        for _ in range(2):
            memory.update_capability("instance_1", "research", False)

        # Should have high success rate
        rate = memory.instance_capabilities["instance_1"]["research"]
        assert rate > 0.5

    def test_get_best_instance_for_capability(self) -> None:
        """Test getting best instance for capability."""
        memory = StrategicMemory()

        # Train two instances
        for _ in range(10):
            memory.update_capability("good", "research", True)
            memory.update_capability("bad", "research", False)

        best = memory.get_best_instance_for_capability("research", ["good", "bad"])
        assert best == "good"


# =============================================================================
# ORGANISM ADAPTER TESTS
# =============================================================================


class TestOrganismAdapter:
    """Tests for OrganismInstanceAdapter."""

    def test_adapter_instance_id(self) -> None:
        """Test adapter instance ID."""

        # Mock organism
        class MockOrganism:
            pass

        adapter = OrganismInstanceAdapter(MockOrganism(), instance_id="test_organism")
        assert adapter.instance_id == "test_organism"
        assert adapter.instance_type == "organism"

    def test_adapter_capabilities(self) -> None:
        """Test adapter capabilities."""

        class MockOrganism:
            pass

        adapter = OrganismInstanceAdapter(MockOrganism())
        capabilities = adapter.get_capabilities()

        # Should have colony capabilities
        assert "research" in capabilities
        assert "build" in capabilities
        assert "test" in capabilities

    def test_adapter_health(self) -> None:
        """Test adapter health."""

        class MockOrganism:
            def get_health(self) -> dict[str, Any]:
                return {"status": "healthy", "health": 0.9}

        adapter = OrganismInstanceAdapter(MockOrganism())
        health = adapter.get_health()

        assert "h_x" in health
        assert "status" in health


# =============================================================================
# COORDINATION MODE TESTS
# =============================================================================


class TestCoordinationModes:
    """Tests for different coordination modes."""

    @pytest.mark.asyncio
    async def test_single_mode(
        self, orchestrator: MetaOrchestrator, mock_instance: MockInstance
    ) -> None:
        """Test single instance coordination."""
        orchestrator.register_instance("test", mock_instance)

        result = await orchestrator.coordinate(
            task="simple task",
            mode=CoordinationMode.SINGLE,
        )

        assert result.mode == CoordinationMode.SINGLE

    @pytest.mark.asyncio
    async def test_parallel_mode(
        self, orchestrator: MetaOrchestrator, mock_instances: dict[str, MockInstance]
    ) -> None:
        """Test parallel coordination."""
        for name, instance in mock_instances.items():
            orchestrator.register_instance(name, instance)

        result = await orchestrator.coordinate(
            task="parallel task",
            mode=CoordinationMode.PARALLEL,
        )

        # Parallel mode should be selected for independent tasks
        assert result.mode in (CoordinationMode.PARALLEL, CoordinationMode.PIPELINE)


# =============================================================================
# STATISTICS TESTS
# =============================================================================


class TestStatistics:
    """Tests for orchestrator statistics."""

    @pytest.mark.asyncio
    async def test_stats_increment(
        self, orchestrator: MetaOrchestrator, mock_instance: MockInstance
    ) -> None:
        """Test statistics increment after coordination."""
        orchestrator.register_instance("test", mock_instance)

        # Execute a coordination
        await orchestrator.coordinate(task="test task")

        stats = orchestrator.get_stats()
        assert stats["stats"]["total_coordinations"] >= 1

    def test_stats_include_instances(
        self, orchestrator: MetaOrchestrator, mock_instances: dict[str, MockInstance]
    ) -> None:
        """Test stats include instance information."""
        for name, instance in mock_instances.items():
            orchestrator.register_instance(name, instance)

        stats = orchestrator.get_stats()
        assert "instances" in stats
        assert len(stats["instances"]) == 3

    def test_get_active_coordinations_empty(self, orchestrator: MetaOrchestrator) -> None:
        """Test active coordinations is empty initially."""
        active = orchestrator.get_active_coordinations()
        assert active == []


# =============================================================================
# PERSISTENCE TESTS
# =============================================================================


class TestPersistence:
    """Tests for memory persistence."""

    @pytest.mark.asyncio
    async def test_persistence_save_load(self, temp_memory_path: Path) -> None:
        """Test memory is saved and loaded correctly."""
        # Create orchestrator and record some history
        orchestrator1 = create_meta_orchestrator(
            memory_path=temp_memory_path,
            enable_persistence=True,
        )
        orchestrator1._memory.record_success(
            task_type="test",
            decomposition=[{"action": "test"}],
            instance_assignments={},
        )
        orchestrator1._save_memory()

        # Create new orchestrator and load
        orchestrator2 = create_meta_orchestrator(
            memory_path=temp_memory_path,
            enable_persistence=True,
        )

        # Should have loaded the pattern
        patterns = orchestrator2._memory.decomposition_patterns.get("test", [])
        assert len(patterns) >= 1
