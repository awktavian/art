"""
Comprehensive Tests for Embodied Cognition Layer

Tests sensorimotor prediction, efference copy, and spatial model:
- Sensory prediction generation
- Actual observation capture
- Prediction error computation
- Spatial model updating
- Efference copy storage
- Edge cases
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration


from kagami.core.embodiment import (
    EmbodiedCognitionLayer,
    SensoryObservation,
    SensoryPrediction,
)


class TestSensoryPrediction:
    """Test sensory consequence prediction"""

    @pytest.mark.asyncio
    async def test_predict_forge_generation(self):
        """Test prediction for Forge 3D generation"""
        layer = EmbodiedCognitionLayer()

        action = {
            "app": "forge",
            "action": "generate",
            "params": {"prompt": "character"},
        }

        prediction = await layer.predict_sensory_consequence(action)

        assert prediction.expected_artifact_type == "3D_mesh"
        assert prediction.expected_vertices_range[0] > 0
        assert prediction.expected_file_size_mb[0] > 0
        assert prediction.expected_duration_seconds[0] > 0

    @pytest.mark.asyncio
    async def test_predict_file_upload(self):
        """Test prediction for file upload"""
        layer = EmbodiedCognitionLayer()

        action = {
            "app": "files",
            "action": "upload",
            "params": {"file_path": "test.jpg"},
        }

        prediction = await layer.predict_sensory_consequence(action)

        assert prediction.expected_artifact_type == "file"
        assert prediction.expected_duration_seconds[1] > prediction.expected_duration_seconds[0]

    @pytest.mark.asyncio
    async def test_predict_unknown_action(self):
        """Test prediction for unknown action type"""
        layer = EmbodiedCognitionLayer()

        action = {"app": "unknown", "action": "unknown_action"}

        prediction = await layer.predict_sensory_consequence(action)

        # Should return default prediction
        assert prediction is not None

    @pytest.mark.asyncio
    async def test_predict_empty_action(self):
        """Test prediction with empty action"""
        layer = EmbodiedCognitionLayer()

        action = {}

        prediction = await layer.predict_sensory_consequence(action)

        assert prediction is not None


class TestSensoryObservation:
    """Test actual sensory observation capture"""

    @pytest.mark.asyncio
    async def test_observe_successful_generation(self):
        """Test observation of successful artifact generation"""
        layer = EmbodiedCognitionLayer()

        action = {"app": "forge", "action": "generate"}
        result = {
            "artifact": {"type": "3D_mesh", "vertices": 15000, "file_size_mb": 3.5},
            "duration_ms": 8000,
        }

        observation = await layer.sense_actual_consequence(action, result)

        assert observation.actual_artifact_type == "3D_mesh"
        assert observation.actual_vertices == 15000
        assert observation.actual_file_size_mb == 3.5
        assert observation.actual_duration_seconds == 8.0

    @pytest.mark.asyncio
    async def test_observe_empty_result(self):
        """Test observation with empty result"""
        layer = EmbodiedCognitionLayer()

        action = {"app": "test", "action": "test"}
        result = {}

        observation = await layer.sense_actual_consequence(action, result)

        assert observation is not None
        assert observation.actual_artifact_type == ""

    @pytest.mark.asyncio
    async def test_observe_partial_artifact(self):
        """Test observation with partial artifact data"""
        layer = EmbodiedCognitionLayer()

        action = {"app": "test", "action": "test"}
        result = {
            "artifact": {"type": "partial"}
            # Missing vertices, file_size_mb
        }

        observation = await layer.sense_actual_consequence(action, result)

        assert observation.actual_artifact_type == "partial"
        assert observation.actual_vertices == 0
        assert observation.actual_file_size_mb == 0


class TestSpatialModelUpdate:
    """Test spatial model updating from predictions and observations"""

    @pytest.mark.asyncio
    async def test_update_from_accurate_prediction(self):
        """Test update when prediction is accurate"""
        layer = EmbodiedCognitionLayer()

        prediction = SensoryPrediction(
            expected_artifact_type="3D_mesh",
            expected_vertices_range=(10000, 20000),
            expected_file_size_mb=(2, 5),
            expected_duration_seconds=(5, 10),
        )

        observation = SensoryObservation(
            actual_artifact_type="3D_mesh",
            actual_vertices=15000,  # Within predicted range
            actual_file_size_mb=3.5,
            actual_duration_seconds=7.0,
        )

        await layer.update_spatial_model(prediction, observation)

        # Check efference copy was stored
        assert len(layer._efference_copies) == 1
        efference = layer._efference_copies[0]
        assert efference.prediction_error["vertices_error"] < 10000  # Relatively small error

    @pytest.mark.asyncio
    async def test_update_from_inaccurate_prediction(self):
        """Test update when prediction is inaccurate"""
        layer = EmbodiedCognitionLayer()

        prediction = SensoryPrediction(
            expected_artifact_type="3D_mesh",
            expected_vertices_range=(5000, 10000),
            expected_file_size_mb=(1, 2),
            expected_duration_seconds=(2, 4),
        )

        observation = SensoryObservation(
            actual_artifact_type="3D_mesh",
            actual_vertices=50000,  # Much more than predicted
            actual_file_size_mb=15.0,
            actual_duration_seconds=30.0,
        )

        await layer.update_spatial_model(prediction, observation)

        # Check large error was recorded
        assert len(layer._efference_copies) == 1
        efference = layer._efference_copies[0]
        assert efference.prediction_error["vertices_error"] > 30000
        assert efference.prediction_error["duration_error"] > 20

    @pytest.mark.asyncio
    async def test_multiple_updates(self):
        """Test multiple sequential updates"""
        layer = EmbodiedCognitionLayer()

        for i in range(10):
            prediction = SensoryPrediction(
                expected_vertices_range=(1000 * i, 1000 * (i + 1)),
                expected_duration_seconds=(i, i + 1),
            )
            observation = SensoryObservation(
                actual_vertices=1000 * i + 500, actual_duration_seconds=i + 0.5
            )

            await layer.update_spatial_model(prediction, observation)

        # All efference copies should be stored
        assert len(layer._efference_copies) == 10

    @pytest.mark.asyncio
    async def test_efference_copy_maxlen(self):
        """Test efference copy buffer respects maxlen"""
        layer = EmbodiedCognitionLayer()

        # Add more than maxlen (100) entries
        for _i in range(150):
            prediction = SensoryPrediction()
            observation = SensoryObservation()

            await layer.update_spatial_model(prediction, observation)

        # Should only keep last 100
        assert len(layer._efference_copies) == 100


class TestSpatialState:
    """Test spatial state querying"""

    @pytest.mark.asyncio
    async def test_get_initial_state(self):
        """Test getting state with no updates"""
        layer = EmbodiedCognitionLayer()

        state = layer.get_spatial_state()

        assert "model" in state
        assert "efference_copies" in state
        assert "timestamp" in state
        assert state["efference_copies"] == 0

    @pytest.mark.asyncio
    async def test_get_state_after_updates(self):
        """Test getting state after some updates"""
        layer = EmbodiedCognitionLayer()

        # Add some efference copies
        for _i in range(5):
            await layer.update_spatial_model(SensoryPrediction(), SensoryObservation())

        state = layer.get_spatial_state()

        assert state["efference_copies"] == 5
        assert state["timestamp"] > 0


class TestEmbodiedCognitionEdgeCases:
    """Test edge cases and error conditions"""

    @pytest.mark.asyncio
    async def test_none_observations(self):
        """Test handling of None values in observations"""
        layer = EmbodiedCognitionLayer()

        observation = SensoryObservation(
            actual_vertices=None,
            actual_file_size_mb=None,
            actual_duration_seconds=0,
        )

        prediction = SensoryPrediction(
            expected_vertices_range=(1000, 2000), expected_duration_seconds=(5, 10)
        )

        # Should not crash
        await layer.update_spatial_model(prediction, observation)

    @pytest.mark.asyncio
    async def test_negative_values(self):
        """Test handling of unexpected negative values"""
        layer = EmbodiedCognitionLayer()

        observation = SensoryObservation(
            actual_vertices=-100,
            actual_duration_seconds=-5,  # Invalid  # Invalid
        )

        prediction = SensoryPrediction(
            expected_vertices_range=(1000, 2000), expected_duration_seconds=(5, 10)
        )

        # Should handle gracefully
        await layer.update_spatial_model(prediction, observation)

    @pytest.mark.asyncio
    async def test_very_large_errors(self):
        """Test handling of very large prediction errors"""
        layer = EmbodiedCognitionLayer()

        prediction = SensoryPrediction(
            expected_vertices_range=(1000, 2000), expected_duration_seconds=(1, 2)
        )

        observation = SensoryObservation(
            actual_vertices=1000000000,  # Billion vertices
            actual_duration_seconds=86400,  # 24 hours
        )

        # Should not crash
        await layer.update_spatial_model(prediction, observation)

        efference = layer._efference_copies[0]
        assert efference.prediction_error["vertices_error"] > 999998000
        assert efference.prediction_error["duration_error"] > 86000


class TestEmbodiedCognitionIntegration:
    """Test integration scenarios"""

    @pytest.mark.asyncio
    async def test_full_sensorimotor_loop(self):
        """Test complete sensorimotor prediction → action → observation cycle"""
        layer = EmbodiedCognitionLayer()

        # 1. Predict sensory consequence
        action = {"app": "forge", "action": "generate"}
        prediction = await layer.predict_sensory_consequence(action)

        # 2. "Execute" action (simulated)
        result = {
            "artifact": {"type": "3D_mesh", "vertices": 12000, "file_size_mb": 2.5},
            "duration_ms": 6500,
        }

        # 3. Observe actual consequence
        observation = await layer.sense_actual_consequence(action, result)

        # 4. Update spatial model
        await layer.update_spatial_model(prediction, observation)

        # Verify loop completed
        assert len(layer._efference_copies) == 1
        state = layer.get_spatial_state()
        assert state["efference_copies"] == 1

    @pytest.mark.asyncio
    async def test_learning_from_repeated_actions(self):
        """Test that repeated similar actions build history"""
        layer = EmbodiedCognitionLayer()

        # Simulate 20 similar actions
        for i in range(20):
            action = {"app": "forge", "action": "generate"}
            prediction = await layer.predict_sensory_consequence(action)

            observation = SensoryObservation(
                actual_artifact_type="3D_mesh",
                actual_vertices=10000 + i * 100,
                actual_duration_seconds=5.0 + i * 0.1,
            )

            await layer.update_spatial_model(prediction, observation)

        # Should have history of 20 actions
        assert len(layer._efference_copies) == 20

        # Model should have learned patterns
        state = layer.get_spatial_state()
        assert state["efference_copies"] == 20
