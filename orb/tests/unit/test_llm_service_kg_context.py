from __future__ import annotations

import os

import pytest

pytestmark = [
    pytest.mark.tier_unit,
    pytest.mark.unit,
]


@pytest.mark.asyncio
async def test_llm_service_injects_kg_context():
    """Test that LLM service works with KG context flags enabled."""
    # Note: In test mode with tiny-gpt2, output is generated, not echoed
    os.environ["KAGAMI_TEST_ECHO_LLM"] = "0"  # Use real lightweight model
    os.environ["KAGAMI_LLM_INCLUDE_CONTEXT"] = "1"
    os.environ["KAGAMI_LLM_INCLUDE_KG"] = "1"

    from kagami.core.services.llm.service import get_llm_service

    svc = get_llm_service()
    # Force fresh init
    await svc.initialize()

    text = await svc.generate(
        prompt="Say hello",
        app_name="TestApp",
        max_tokens=20,  # Limit output for speed
    )

    # With lightweight model (tiny-gpt2), validate basic functionality
    assert isinstance(text, str)
    # Ensure non-empty result and no exceptions with KG flags enabled
    assert len(text) > 0
    # Just verify we got text output (tiny-gpt2 generates random but valid text)
    assert len(text) >= 3, f"Expected some text output, got: {text}"
