
from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_unit


import asyncio
import time


@pytest.mark.asyncio
async def test_agent_graph_records_and_neighbors():
    """Test agent graph records collaborations and finds neighbors.

    FIXED: Now uses reset_singletons fixture (autouse) instead of manual reset.
    """
    from kagami.core.swarm import agent_graph

    # Get fresh graph (reset_singletons fixture ensures clean state)
    graph = agent_graph.get_agent_graph()

    # Record multiple collaborations to build synergy above threshold
    # With EMA (alpha=0.3), first collab gives: 0.3*0.9 + 0.7*0.5 = 0.62
    # Second: 0.3*0.9 + 0.7*0.62 = 0.704 (above threshold!)
    await graph.record_collaboration("sage", "optimizer", outcome_quality=0.9, task_type="optimize")
    await graph.record_collaboration("sage", "optimizer", outcome_quality=0.9, task_type="optimize")

    neighbors = graph.get_neighbors("sage", threshold=0.7)
    assert "optimizer" in neighbors
