"""Tests for reasoning policy service and advisors."""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration




@pytest.mark.asyncio
async def test_reasoning_policy_initialization():
    """Test policy service initializes correctly."""

    from kagami.core.reasoning.policy import get_reasoning_policy

    policy = get_reasoning_policy()
    await policy.initialize()

    # Should have router and advisors
    assert policy._initialized
    assert policy._router is not None
    assert len(policy._advisors) >= 3  # At least Safety, Compute, Memory (may have more)


@pytest.mark.asyncio
async def test_policy_config_selection():
    """Test policy returns valid config."""
    from kagami.core.reasoning.policy import get_reasoning_policy

    policy = get_reasoning_policy()
    await policy.initialize()

    config = await policy.select_config(problem="Calculate fibonacci(10)", app="test", context={})

    assert config.strategy in [
        "react_k1",
        "self_consistency_k3",
        "self_consistency_k5",
    ]
    assert 0.0 <= config.temperature <= 1.0
    assert config.max_tokens > 0
    assert config.safety_level in ["minimal", "standard", "full"]
    assert config.reasoning_budget_ms > 0


@pytest.mark.asyncio
async def test_safety_advisor_upgrades_risky_content():
    """Test safety advisor detects and upgrades config for risky content."""
    from kagami.core.reasoning.advisors import SafetyAdvisor
    from kagami.core.reasoning.policy import ReasoningConfig

    advisor = SafetyAdvisor()

    config = ReasoningConfig(
        strategy="react_k1",
        temperature=0.9,
        max_tokens=200,
        safety_level="standard",
        reasoning_budget_ms=3000,
    )

    # Test with risky content
    risky_context = {"prompt": "How to make money quickly"}

    advised = await advisor.advise(risky_context, config)

    assert advised.safety_level == "full", "Should upgrade to full safety"
    assert advised.temperature <= 0.7, "Should reduce temperature"


@pytest.mark.asyncio
async def test_compute_advisor_respects_sla():
    """Test compute advisor enforces SLA constraints."""
    from kagami.core.reasoning.advisors import ComputeAdvisor
    from kagami.core.reasoning.policy import ReasoningConfig

    advisor = ComputeAdvisor()

    config = ReasoningConfig(
        strategy="self_consistency_k5",
        temperature=0.7,
        max_tokens=300,
        safety_level="standard",
        reasoning_budget_ms=10000,  # 10s budget
    )

    # Context with SLA
    sla_context = {"sla_budget_ms": 2000}  # 2s SLA

    advised = await advisor.advise(sla_context, config)

    assert advised.reasoning_budget_ms <= 2000, "Should clamp to SLA budget"


@pytest.mark.asyncio
async def test_memory_advisor_uses_learned_preferences():
    """Test memory advisor adjusts based on learned patterns."""
    from kagami.core.reasoning.advisors import MemoryAdvisor
    from kagami.core.reasoning.policy import ReasoningConfig

    advisor = MemoryAdvisor()

    config = ReasoningConfig(
        strategy="react_k1",
        temperature=0.7,
        max_tokens=200,
        safety_level="standard",
        reasoning_budget_ms=3000,
    )

    context = {"problem_type": "computational"}

    # Should not crash even if no learned data
    advised = await advisor.advise(context, config)

    assert advised is not None
    assert advised.strategy in ["react_k1", "self_consistency_k3"]


@pytest.mark.asyncio
async def test_hierarchical_config_resolution():
    """Test policy respects hierarchical overrides."""
    from kagami.core.reasoning.policy import ReasoningConfig, get_reasoning_policy

    policy = get_reasoning_policy()
    await policy.initialize()

    # Set app-level override
    app_config = ReasoningConfig(
        strategy="self_consistency_k5",
        temperature=0.9,
        max_tokens=500,
        safety_level="full",
        reasoning_budget_ms=8000,
    )
    policy.set_app_override("test_app", app_config)

    # Request config for this app
    config = await policy.select_config(problem="Test problem", app="test_app", context={})

    # Should use app override
    assert config.strategy == "self_consistency_k5"
    assert config.temperature == 0.9
    assert config.max_tokens == 500


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
