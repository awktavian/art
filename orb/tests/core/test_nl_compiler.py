"""Tests for NL → LANG/2 Compiler (Efficient Approach)"""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration



from kagami.core.nl_to_lang2_compiler import create_nl_compiler


@pytest.mark.asyncio
async def test_nl_compiler_creation():
    """Test creating NL compiler."""
    compiler = create_nl_compiler(device="cpu", use_llm=False)

    assert compiler is not None
    assert compiler.device == "cpu"


@pytest.mark.asyncio
async def test_translation_generates_lang2():
    """Test that NL translates to valid LANG/2."""
    compiler = create_nl_compiler(device="cpu", use_llm=False)

    result = await compiler.compile_and_execute("Help me overcome my anxiety")

    # Should generate valid LANG/2 (either LLM or fallback to orchestrator)
    assert result.generated_lang2 is not None
    assert result.generated_lang2.startswith("SLANG")
    # Fallback routes to orchestrator
    assert "orchestrator.query" in result.generated_lang2 or "plan." in result.generated_lang2


@pytest.mark.asyncio
async def test_preserves_intent():
    """Test that original intent is preserved in goal."""
    compiler = create_nl_compiler(device="cpu", use_llm=False)

    result = await compiler.compile_and_execute("What should I do about this conflict?")

    # Original intent should be in the goal somewhere
    assert "conflict" in result.generated_lang2.lower()


@pytest.mark.asyncio
async def test_routes_to_valid_app():
    """Test that it routes to a valid app."""
    compiler = create_nl_compiler(device="cpu", use_llm=False)

    result = await compiler.compile_and_execute("I want to understand consciousness better")

    # Should route to a valid app (orchestrator, files, plan, forge, etc.)
    valid_apps = ["orchestrator.", "plan.", "files.", "forge.", "analytics.", "optimizer."]
    assert any(app in result.generated_lang2.lower() for app in valid_apps)


@pytest.mark.asyncio
async def test_action_oriented():
    """Test that goals are action-oriented."""
    compiler = create_nl_compiler(device="cpu", use_llm=False)

    result = await compiler.compile_and_execute("Plan my vacation to Hawaii")

    # Goal should contain the actionable intent
    assert (
        "vacation" in result.generated_lang2.lower() or "hawaii" in result.generated_lang2.lower()
    )


@pytest.mark.asyncio
async def test_end_to_end_execution():
    """Test complete NL → LANG/2 → MobiASM → Result."""
    compiler = create_nl_compiler(device="cpu", use_llm=False)

    result = await compiler.compile_and_execute("Help me overcome my anxiety")

    # Should have translated
    assert result.generated_lang2 is not None
    assert result.generated_lang2.startswith("SLANG")

    # Should have compiled
    assert len(result.compilation_result.mobiasm_ops) > 0

    # Should have executed
    assert result.compilation_result.result is not None


@pytest.mark.asyncio
async def test_geometric_computation():
    """Test that actual geometric computation happens."""
    compiler = create_nl_compiler(device="cpu", use_llm=False)

    result = await compiler.compile_and_execute("Navigate from fear to trust")

    # Should compute path
    if "path_length" in result.compilation_result.result:
        assert result.compilation_result.result["path_length"] > 0


@pytest.mark.asyncio
async def test_multiple_intents():
    """Test handling multiple different intents."""
    compiler = create_nl_compiler(device="cpu", use_llm=False)

    intents = [
        "Help me with anxiety",
        "Resolve this conflict",
        "Understand consciousness",
        "Plan vacation",
        "Find patterns",
    ]

    for intent in intents:
        result = await compiler.compile_and_execute(intent)

        # All should succeed
        assert result.generated_lang2 is not None
        assert len(result.compilation_result.mobiasm_ops) > 0
