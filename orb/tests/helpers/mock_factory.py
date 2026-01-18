"""Mock Factory - Reusable mocks for common K os patterns.

Centralized mock creation to ensure consistency and reduce duplication.
"""

import torch
from unittest.mock import AsyncMock, MagicMock

# Set seed for reproducibility
torch.manual_seed(42)


class MockFactory:
    """Factory for creating common test mocks."""

    @staticmethod
    def create_cbf(safe: bool = True) -> MagicMock:
        """Create Control Barrier Function mock.

        Args:
            safe: If True, h_x > 0 (safe). If False, h_x < 0 (unsafe).

        Returns:
            Mocked CBF with barrier_function
        """
        cbf = MagicMock()
        cbf.barrier_function = MagicMock(return_value=0.5 if safe else -0.5)
        cbf.check_safety = MagicMock(return_value=safe)
        return cbf

    @staticmethod
    def create_ethical_instinct(permissible: bool = True) -> MagicMock:
        """Create Ethical Instinct mock.

        Args:
            permissible: If True, allows action. If False, blocks.

        Returns:
            Mocked EthicalInstinct with evaluate
        """
        instinct = MagicMock()
        verdict = MagicMock()
        verdict.permissible = permissible
        verdict.reasoning = "Test verdict" if permissible else "Blocked by policy"
        instinct.evaluate = AsyncMock(return_value=verdict)
        return instinct

    @staticmethod
    def create_fastapi_router() -> MagicMock:
        """Create FastAPI Router mock.

        Returns:
            Mocked APIRouter with proper spec
        """
        from fastapi import APIRouter

        router = MagicMock(spec=APIRouter)
        router.routes = []
        router.prefix = ""
        router.tags = []
        return router

    @staticmethod
    def create_fastapi_app() -> MagicMock:
        """Create FastAPI app mock.

        Returns:
            Mocked FastAPI app with include_router
        """
        from fastapi import FastAPI

        app = MagicMock(spec=FastAPI)
        app.routes = []
        app.include_router = MagicMock()
        return app

    @staticmethod
    def create_brain_api(confidence: float = 0.85) -> MagicMock:
        """Create BrainAPI mock with Matryoshka layers.

        Args:
            confidence: Confidence score (0-1)

        Returns:
            Mocked BrainAPI with 7-layer response
        """
        import torch

        brain = MagicMock()
        brain.encode = MagicMock(return_value=torch.randn(1, 32))
        response = MagicMock()
        activation_value = 5.0 if confidence > 0.5 else -5.0
        response.final_output = torch.ones(1, 2048) * activation_value
        response.activations = [
            torch.randn(1, 32),
            torch.randn(1, 64),
            torch.randn(1, 128),
            torch.randn(1, 256),
            torch.randn(1, 512),
            torch.randn(1, 1024),
            torch.randn(1, 2048),
        ]
        brain.query = AsyncMock(return_value=response)
        return brain

    @staticmethod
    def create_world_model() -> MagicMock:
        """Create MatryoshkaBrain world model mock.

        Returns:
            Mocked world model with predict and encode_text
        """
        import torch

        model = MagicMock()
        model.predict = AsyncMock(return_value=torch.randn(1, 768))
        model.encode_text = AsyncMock(return_value=torch.randn(1, 768))
        return model

    @staticmethod
    def create_curriculum_learning() -> MagicMock:
        """Create CurriculumLearningSystem mock.

        Returns:
            Mocked curriculum with add_experience
        """
        curriculum = MagicMock()
        curriculum.add_experience = AsyncMock()
        return curriculum

    @staticmethod
    def create_geometric_worker(agent_id: str = "test_agent") -> MagicMock:
        """Create GeometricWorker mock.

        Args:
            agent_id: Worker identifier

        Returns:
            Mocked GeometricWorker
        """
        from kagami.core.unified_agents import GeometricWorker

        agent = MagicMock(spec=GeometricWorker)
        agent.worker_id = agent_id
        agent.execute = AsyncMock(return_value={"status": "success"})
        return agent

    @staticmethod
    def create_task(action: str = "test_action", priority: float = 0.8) -> MagicMock:
        """Create Task mock.

        Args:
            action: Task action string
            priority: Task priority (0-1)

        Returns:
            Mocked Task
        """
        from kagami.core.unified_agents import Task

        task = MagicMock(spec=Task)
        task.action = action
        task.params = {"key": "value"}
        task.priority = priority
        return task

    @staticmethod
    def create_organism() -> MagicMock:
        """Create organism mock.

        Returns:
            Mocked organism with execute_intent
        """
        organism = MagicMock()
        organism.execute_intent = AsyncMock(
            return_value={"result": "Task completed successfully", "status": "success"}
        )
        return organism

    @staticmethod
    def create_composio_service() -> MagicMock:
        """Create Composio service mock.

        Returns:
            Mocked Composio with execute
        """
        service = MagicMock()
        service.initialize = AsyncMock()
        service.execute = AsyncMock(return_value={"success": True})
        return service
