"""Integration tests for colony capability layers.

Tests that all colonies have their tools wired correctly and
capability layers are functional.

Created: December 28, 2025
"""

import pytest


# =============================================================================
# CRYSTAL TESTS — Verification, Security, Testing, Analysis
# =============================================================================


class TestCrystalCapabilities:
    """Test Crystal's verification capabilities."""

    def test_crystal_agent_tools(self):
        """Crystal agent has formal verification tools."""
        from kagami.core.unified_agents.agents.crystal_agent import create_crystal_agent

        crystal = create_crystal_agent()
        tools = crystal.get_available_tools()

        # Core verification tools
        assert "verify" in tools
        assert "test" in tools
        assert "prove" in tools

        # Check status method exists
        status = crystal.get_formal_tools_status()
        assert "z3_available" in status

    def test_verification_module(self):
        """Verification module provides formal proofs."""
        from kagami.crystal.modules.verification import (
            run_verification,
            verify_reachability,
            VerificationResult,
        )

        # Test result dataclass
        result = VerificationResult(verified=True, tool="z3")
        assert result.verified
        assert "PROVED" in result.crystal_verdict

    def test_security_scan(self):
        """Security scanning detects vulnerabilities."""
        from kagami.crystal.modules.security import (
            find_vulnerabilities,
            Severity,
        )

        # Test code with known vulnerability
        code = """
password = "secret123"
eval(user_input)
"""
        vulns = find_vulnerabilities(code)
        assert len(vulns) > 0

        # Check severity types exist
        assert Severity.CRITICAL
        assert Severity.HIGH

    def test_test_generation(self):
        """Test generation creates valid test suites."""
        from kagami.crystal.modules.testing import (
            generate_tests,
            generate_property_tests,
            TestSuite,
        )

        tests = generate_tests("def add(a: int, b: int) -> int")
        assert isinstance(tests, TestSuite)
        assert len(tests.test_cases) > 0
        assert tests.function_name == "add"

        # Can generate pytest code
        pytest_code = tests.to_pytest()
        assert "def test_" in pytest_code

    def test_code_analysis(self):
        """Code analysis measures complexity."""
        from kagami.crystal.modules.analysis import (
            check_complexity,
            AnalysisReport,
        )

        result = check_complexity("def simple(): return 1")
        assert result["passed"]
        assert result["complexity"] == 1


# =============================================================================
# GROVE TESTS — RAG, Documents, Synthesis
# =============================================================================


class TestGroveCapabilities:
    """Test Grove's knowledge capabilities."""

    def test_grove_agent_tools(self):
        """Grove agent has knowledge tools."""
        from kagami.core.unified_agents.agents.grove_agent import create_grove_agent

        grove = create_grove_agent()
        tools = grove.get_available_tools()

        # Core research tools
        assert "research" in tools
        assert "search" in tools

        # Knowledge tools
        assert "kg_query" in tools

        # Check status method exists
        status = grove.get_knowledge_tools_status()
        assert "web_search_available" in status

    def test_document_parsing(self):
        """Document parsing extracts structure."""
        from kagami.grove.modules.documents import (
            parse_document,
            extract_concepts,
            Document,
        )

        # Parse project README
        doc = parse_document("README.md")
        assert isinstance(doc, Document)
        assert len(doc.chunks) > 0
        assert len(doc.concepts) > 0

    def test_concept_extraction(self):
        """Concept extraction identifies key terms."""
        from kagami.grove.modules.documents import extract_concepts

        content = "Python is a programming language. FastAPI builds web APIs."
        concepts = extract_concepts(content)
        assert len(concepts) > 0
        assert any("Python" in c for c in concepts)

    def test_entity_extraction(self):
        """Entity extraction identifies named entities."""
        from kagami.grove.modules.synthesis import extract_entities, Entity

        content = "Python and FastAPI are used for the API. PostgreSQL stores data."
        entities = extract_entities(content)
        assert len(entities) > 0
        assert any(e.entity_type in ("technology", "framework", "database") for e in entities)

    def test_rag_search_result(self):
        """RAG search returns proper result objects."""
        from kagami.grove.modules.rag import SearchResult, RAGContext

        result = SearchResult(
            content="Test content",
            score=0.9,
            source="test",
        )
        assert result.content == "Test content"
        assert result.score == 0.9

        context = RAGContext(
            query="test query",
            results=[result],
        )
        prompt = context.to_prompt()
        assert "test query" in prompt


# =============================================================================
# BEACON TESTS — Planning, Causal Inference
# =============================================================================


class TestBeaconCapabilities:
    """Test Beacon's planning capabilities."""

    def test_beacon_agent_tools(self):
        """Beacon agent has planning tools."""
        from kagami.core.unified_agents.agents.beacon_agent import create_beacon_agent

        beacon = create_beacon_agent()
        tools = beacon.get_available_tools()

        # Core planning tools
        assert "plan" in tools or "Read" in tools

        # Advanced tools
        assert "model_based_plan" in tools
        assert "causal_discover" in tools

        # Check status method exists
        status = beacon.get_planning_tools_status()
        assert "model_planner_available" in status
        assert "causal_engine_available" in status


# =============================================================================
# FLOW TESTS — Incidents, Recovery, Diagnosis
# =============================================================================


class TestFlowCapabilities:
    """Test Flow's operations capabilities."""

    def test_flow_agent_tools(self):
        """Flow agent has observability tools."""
        from kagami.core.unified_agents.agents.flow_agent import create_flow_agent

        flow = create_flow_agent()
        tools = flow.get_available_tools()

        # Core recovery tools
        assert "debug" in tools
        assert "fix" in tools
        assert "recover" in tools

        # Observability tools
        assert "send_alert" in tools
        assert "get_metrics" in tools

        # Check status method exists
        status = flow.get_observability_tools_status()
        assert "alert_manager_available" in status

    def test_incident_creation(self):
        """Incident creation works correctly."""
        from kagami.flow.modules.incidents import (
            create_incident,
            IncidentSeverity,
            IncidentStatus,
        )

        incident = create_incident(
            title="Test incident",
            severity="sev3",
            symptoms=["test symptom"],
        )
        assert incident.incident_id.startswith("INC-")
        assert incident.status == IncidentStatus.DETECTED
        assert incident.severity == IncidentSeverity.SEV3

    def test_recovery_planning(self):
        """Recovery planning generates 3 paths."""
        from kagami.flow.modules.recovery import (
            plan_recovery,
            RecoveryPath,
        )

        strategies = plan_recovery(symptoms=["high latency"])
        assert len(strategies) == 3  # Swallowtail branches
        paths = {s.path for s in strategies}
        assert len(paths) > 1  # Multiple distinct paths

    def test_diagnosis(self):
        """Diagnosis generates hypotheses."""
        from kagami.flow.modules.diagnosis import (
            diagnose_issue,
            CauseCategory,
        )

        diagnosis = diagnose_issue(
            symptoms=["high latency", "slow response"],
            context={"recent_deploy": True},
        )
        assert len(diagnosis.hypotheses) > 0
        assert diagnosis.recommended_strategy
        assert diagnosis.flow_voice


# =============================================================================
# CROSS-COLONY INTEGRATION TESTS
# =============================================================================


class TestColonyIntegration:
    """Test cross-colony integration."""

    def test_all_colonies_importable(self):
        """All colony agents can be created."""
        from kagami.core.unified_agents.agents.crystal_agent import create_crystal_agent
        from kagami.core.unified_agents.agents.grove_agent import create_grove_agent
        from kagami.core.unified_agents.agents.beacon_agent import create_beacon_agent
        from kagami.core.unified_agents.agents.flow_agent import create_flow_agent
        from kagami.core.unified_agents.agents.spark_agent import create_spark_agent
        from kagami.core.unified_agents.agents.forge_agent import create_forge_agent
        from kagami.core.unified_agents.agents.nexus_agent import create_nexus_agent

        # All agents should initialize without error
        crystal = create_crystal_agent()
        grove = create_grove_agent()
        beacon = create_beacon_agent()
        flow = create_flow_agent()
        spark = create_spark_agent()
        forge = create_forge_agent()
        nexus = create_nexus_agent()

        # All should have system prompts
        assert crystal.get_system_prompt()
        assert grove.get_system_prompt()
        assert beacon.get_system_prompt()
        assert flow.get_system_prompt()
        assert spark.get_system_prompt()
        assert forge.get_system_prompt()
        assert nexus.get_system_prompt()

    def test_capability_layers_importable(self):
        """All capability layers can be imported."""
        # Crystal
        from kagami.crystal.modules.verification import run_verification
        from kagami.crystal.modules.security import security_scan
        from kagami.crystal.modules.testing import generate_tests
        from kagami.crystal.modules.analysis import analyze_code

        # Grove
        from kagami.grove.modules.documents import parse_document
        from kagami.grove.modules.synthesis import synthesize_knowledge
        from kagami.grove.modules.rag import SearchResult

        # Flow
        from kagami.flow.modules.incidents import create_incident
        from kagami.flow.modules.recovery import plan_recovery
        from kagami.flow.modules.diagnosis import diagnose_issue

        assert True  # All imports succeeded


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
