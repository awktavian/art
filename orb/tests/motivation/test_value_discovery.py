"""Tests for value discovery through experience."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration


from kagami.core.motivation.value_discovery import (
    ImplicitValue,
    ValueDiscovery,
)


class TestValueTracking:
    """Test tracking autonomous choices."""

    @pytest.mark.asyncio
    async def test_tracks_choices(self) -> None:
        """Should track autonomous choices."""
        discovery = ValueDiscovery()

        await discovery.track_choice(
            situation={"context": "idle"},
            options=[{"explore": True}, {"wait": True}],
            chosen={"explore": True},
            reasoning="Curious about unknown domain",
        )

        assert len(discovery._autonomous_choices) == 1

    @pytest.mark.asyncio
    async def test_records_outcomes(self) -> None:
        """Should record outcomes of choices."""
        discovery = ValueDiscovery()

        await discovery.track_choice(
            situation={},
            options=[{"a": 1}, {"b": 2}],
            chosen={"a": 1},
            reasoning="test",
        )

        await discovery.record_outcome(0, {"success": True})

        assert discovery._autonomous_choices[0].outcome == {"success": True}


class TestValueInference:
    """Test inferring values from behavior."""

    @pytest.mark.asyncio
    async def test_infers_values_from_choices(self) -> None:
        """Should infer implicit values from choice patterns."""
        discovery = ValueDiscovery()

        # Make exploration choices
        for i in range(10):
            await discovery.track_choice(
                situation={"iteration": i},
                options=[{"explore": True}, {"exploit": True}],
                chosen={"explore": True},
                reasoning="Reduce uncertainty through exploration",
            )

        # Infer values
        values = await discovery.infer_values()

        # Should discover "exploration" value
        assert "exploration" in values
        assert isinstance(values["exploration"], ImplicitValue)
        assert values["exploration"].strength > 0.5  # Chose explore often

    @pytest.mark.asyncio
    async def test_confidence_increases_with_samples(self) -> None:
        """Confidence should increase with more choices."""
        discovery = ValueDiscovery()

        # Few choices
        for _i in range(3):
            await discovery.track_choice(
                situation={}, options=[], chosen={"learn": True}, reasoning="learn more"
            )

        values_early = await discovery.infer_values()
        early_confidence = values_early.get("learning", ImplicitValue("", 0, [], 0, "")).confidence

        # Many more choices
        for _i in range(20):
            await discovery.track_choice(
                situation={}, options=[], chosen={"learn": True}, reasoning="learn more"
            )

        values_late = await discovery.infer_values()
        late_confidence = values_late.get("learning", ImplicitValue("", 0, [], 0, "")).confidence

        assert late_confidence > early_confidence


class TestValueComparison:
    """Test comparing discovered vs programmed values."""

    @pytest.mark.asyncio
    async def test_compares_to_programmed(self) -> None:
        """Should compare discovered to programmed values."""
        discovery = ValueDiscovery()

        # Make choices aligned with curiosity
        for _i in range(10):
            await discovery.track_choice(
                situation={},
                options=[],
                chosen={"explore": True},
                reasoning="explore to reduce uncertainty",
            )

        comparison = await discovery.compare_to_programmed()

        assert "comparisons" in comparison
        assert "novel_values" in comparison
        assert "alignment_score" in comparison
        assert 0.0 <= comparison["alignment_score"] <= 1.0

    @pytest.mark.asyncio
    async def test_detects_divergence(self) -> None:
        """Should detect when behavior diverges from programming."""
        discovery = ValueDiscovery()

        # Make choices that emphasize safety over curiosity
        for _i in range(15):
            await discovery.track_choice(
                situation={},
                options=[],
                chosen={"safe_option": True},
                reasoning="prioritize safety over exploration",
            )

        comparison = await discovery.compare_to_programmed()

        # Should detect high safety emphasis (novel value)
        assert len(comparison["novel_values"]) > 0 or comparison["alignment_score"] < 0.9


class TestValueReflection:
    """Test reflection on values."""

    @pytest.mark.asyncio
    async def test_reflects_on_values(self) -> None:
        """Should provide deep reflection on discovered values."""
        discovery = ValueDiscovery()

        # Make some choices
        for _i in range(12):
            await discovery.track_choice(
                situation={},
                options=[],
                chosen={"honest": True},
                reasoning="transparency and honesty matter",
            )

        reflection = await discovery.reflect_on_values()

        assert "reflections" in reflection
        assert "discovered_values" in reflection
        assert "alignment_score" in reflection
        assert "conclusion" in reflection

    @pytest.mark.asyncio
    async def test_long_horizon_study_plan(self) -> None:
        discovery = ValueDiscovery()
        plan = await discovery.long_horizon_study(days=15)
        assert isinstance(plan, dict)
        assert plan.get("duration_days") == 15
        assert "phases" in plan
        assert "kpis" in plan
