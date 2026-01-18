#!/usr/bin/env python3
"""
Simplified Kagami systems verification - tests existence and instantiation only.

Converted to proper pytest format (was a script with sys.exit at module level).
"""

import pytest
import torch
import torch.nn as nn


class TestSystemsSimple:
    """Test core system instantiation."""

    def test_e8_lattice_quantization(self):
        """E8 Lattice Quantization works."""
        from kagami_math.e8_lattice_quantizer import nearest_e8
        x = torch.randn(2, 8)
        q = nearest_e8(x)
        assert q is not None
        assert q.shape == x.shape

    def test_rssm_world_model(self):
        """RSSM World Model can be instantiated."""
        from kagami.core.world_model.rssm_core import OrganismRSSM
        rssm = OrganismRSSM()
        assert rssm is not None

    def test_cbf_safety(self):
        """Control Barrier Functions can be instantiated."""
        from kagami.core.safety.optimal_cbf import OptimalCBF, OptimalCBFConfig
        cbf = OptimalCBF(OptimalCBFConfig())
        assert cbf is not None

    def test_seven_colony_agents(self):
        """All seven colony agents can be instantiated."""
        from kagami.core.unified_agents.agents.spark_agent import SparkAgent
        from kagami.core.unified_agents.agents.forge_agent import ForgeAgent
        from kagami.core.unified_agents.agents.flow_agent import FlowAgent
        from kagami.core.unified_agents.agents.nexus_agent import NexusAgent
        from kagami.core.unified_agents.agents.beacon_agent import BeaconAgent
        from kagami.core.unified_agents.agents.grove_agent import GroveAgent
        from kagami.core.unified_agents.agents.crystal_agent import CrystalAgent

        agents = [
            SparkAgent(),
            ForgeAgent(),
            FlowAgent(),
            NexusAgent(),
            BeaconAgent(),
            GroveAgent(),
            CrystalAgent(),
        ]
        assert len(agents) == 7
        for agent in agents:
            assert agent is not None

    def test_fano_action_router(self):
        """Fano Action Router can be instantiated."""
        from kagami.core.unified_agents.fano_action_router import FanoActionRouter
        router = FanoActionRouter()
        assert router is not None

    def test_receipt_learning_system(self):
        """Receipt Learning System can be instantiated."""
        from kagami.core.learning.receipt_learning import ReceiptLearningEngine
        from kagami.core.schemas.receipt_schema import Receipt
        engine = ReceiptLearningEngine()
        receipt = Receipt(correlation_id="test-001")
        assert engine is not None
        assert receipt is not None

    def test_strange_loop_mu_self(self):
        """Strange Loop (mu_self) can be instantiated and compute mu_self."""
        from kagami.core.strange_loops.godelian_self_reference import GodelianSelfReference
        base = nn.Linear(8, 8)
        godel = GodelianSelfReference(base_module=base)
        mu_self = godel.encode_self()
        assert mu_self is not None
