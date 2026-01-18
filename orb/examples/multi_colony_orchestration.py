#!/usr/bin/env python3
"""Multi-Colony Orchestration Examples.

Demonstrates how to coordinate multiple colonies using Fano plane routing
for complex tasks that require diverse perspectives and capabilities.

PLAN → EXECUTE → VERIFY workflow with all 7 colonies.

Created: December 14, 2025
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path
from typing import Any

# Add packages to path
sys.path.insert(0, str(Path(__file__).parent.parent / "packages"))

import torch

from kagami.core.unified_agents import (
    UnifiedOrganism,
    ColonyType,
)
from kagami.core.unified_agents.agents import (
    SparkAgent,
    ForgeAgent,
    FlowAgent,
    NexusAgent,
    BeaconAgent,
    GroveAgent,
    CrystalAgent,
)
from kagami.core.unified_agents.fano_action_router import FanoActionRouter
from kagami.core.world_model import KagamiWorldModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OrchestrationExample:
    """Example orchestrations using Fano plane routing."""

    def __init__(self):
        """Initialize the organism with all 7 colonies."""
        # Initialize world model
        self.world_model = KagamiWorldModel(
            state_dim=512,
            action_dim=256,
            hidden_dim=512,
            num_colonies=7,
        )

        # Initialize organism with all colonies
        self.organism = UnifiedOrganism(
            world_model=self.world_model,
            num_colonies=7,
        )

        # Initialize Fano router
        self.router = FanoActionRouter(
            input_dim=512,
            hidden_dim=256,
            output_dim=7,  # One output per colony
        )

        # Initialize all colony agents
        self.colonies = {
            ColonyType.SPARK: SparkAgent(),
            ColonyType.FORGE: ForgeAgent(),
            ColonyType.FLOW: FlowAgent(),
            ColonyType.NEXUS: NexusAgent(),
            ColonyType.BEACON: BeaconAgent(),
            ColonyType.GROVE: GroveAgent(),
            ColonyType.CRYSTAL: CrystalAgent(),
        }

    async def plan_execute_verify_workflow(
        self,
        task: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Complete PLAN → EXECUTE → VERIFY workflow.

        This demonstrates the canonical three-phase workflow:
        1. PLAN: Beacon + Grove + Spark (parallel)
        2. EXECUTE: Forge + Nexus + Flow (sequential as needed)
        3. VERIFY: Crystal (always last)

        Args:
            task: High-level task description
            context: Optional context for the task

        Returns:
            Workflow results including all colony outputs
        """
        logger.info(f"Starting PLAN-EXECUTE-VERIFY workflow for: {task}")
        results = {}

        # ========== PHASE 1: PLAN (Parallel) ==========
        # Launch Beacon, Grove, and Spark in parallel for comprehensive planning
        logger.info("PHASE 1: PLANNING (Beacon + Grove + Spark)")

        planning_tasks = []

        # Beacon: Architecture and high-level planning
        planning_tasks.append(
            self._execute_colony(
                ColonyType.BEACON,
                f"Design architecture for: {task}",
                context,
            )
        )

        # Grove: Research existing patterns and best practices
        planning_tasks.append(
            self._execute_colony(
                ColonyType.GROVE,
                f"Research best practices for: {task}",
                context,
            )
        )

        # Spark: Creative ideation and novel approaches
        planning_tasks.append(
            self._execute_colony(
                ColonyType.SPARK,
                f"Generate creative approaches for: {task}",
                context,
            )
        )

        # Wait for all planning to complete
        planning_results = await asyncio.gather(*planning_tasks)
        results["planning"] = {
            "beacon": planning_results[0],
            "grove": planning_results[1],
            "spark": planning_results[2],
        }

        # Synthesize planning outputs
        planning_synthesis = self._synthesize_planning(results["planning"])
        logger.info(f"Planning synthesis: {planning_synthesis}")

        # ========== PHASE 2: EXECUTE ==========
        logger.info("PHASE 2: EXECUTION (Forge + Nexus + Flow)")

        # Forge: Implementation based on plan
        forge_result = await self._execute_colony(
            ColonyType.FORGE,
            f"Implement based on plan: {planning_synthesis}",
            {**context, "plan": planning_synthesis} if context else {"plan": planning_synthesis},
        )
        results["forge"] = forge_result

        # Nexus: Integration if multiple components
        if self._needs_integration(forge_result):
            nexus_result = await self._execute_colony(
                ColonyType.NEXUS,
                f"Integrate components from: {forge_result}",
                {"components": forge_result},
            )
            results["nexus"] = nexus_result

        # Flow: Debugging/adaptation if issues detected
        if self._needs_debugging(results):
            flow_result = await self._execute_colony(
                ColonyType.FLOW,
                "Debug and adapt implementation",
                {"implementation": results},
            )
            results["flow"] = flow_result

        # ========== PHASE 3: VERIFY ==========
        logger.info("PHASE 3: VERIFICATION (Crystal)")

        # Crystal: Final verification and safety checks
        crystal_result = await self._execute_colony(
            ColonyType.CRYSTAL,
            "Verify implementation safety and correctness",
            {"implementation": results},
        )
        results["verification"] = crystal_result

        # Check safety invariant h(x) ≥ 0
        safety_check = self._verify_safety(crystal_result)
        if not safety_check["safe"]:
            logger.error(f"SAFETY VIOLATION: {safety_check['reason']}")
            raise ValueError(f"Safety invariant violated: {safety_check['reason']}")

        logger.info("Workflow complete - all safety checks passed")
        return results

    async def fano_line_composition(
        self,
        colony1: ColonyType,
        colony2: ColonyType,
        task: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a Fano line composition (two colonies produce a third).

        According to Fano plane algebra:
        - Spark × Forge = Flow (creativity + implementation → adaptation)
        - Spark × Nexus = Beacon (creativity + integration → planning)
        - Spark × Grove = Crystal (creativity + research → verification)
        - Forge × Nexus = Grove (implementation + integration → research)
        - Beacon × Forge = Crystal (planning + implementation → verification)
        - Nexus × Flow = Crystal (integration + adaptation → verification)
        - Beacon × Flow = Grove (planning + adaptation → research)

        Args:
            colony1: First colony
            colony2: Second colony
            task: Task description
            context: Optional context

        Returns:
            Composition results
        """
        logger.info(f"Fano composition: {colony1} × {colony2}")

        # Execute both colonies in parallel
        results = await asyncio.gather(
            self._execute_colony(colony1, task, context),
            self._execute_colony(colony2, task, context),
        )

        # Determine resulting colony from Fano composition
        resulting_colony = self._get_fano_composition(colony1, colony2)

        # Execute resulting colony with combined context
        combined_context = {
            "input1": results[0],
            "input2": results[1],
            **(context or {}),
        }

        final_result = await self._execute_colony(
            resulting_colony,
            f"Synthesize outputs for: {task}",
            combined_context,
        )

        return {
            "colony1": {"type": colony1, "output": results[0]},
            "colony2": {"type": colony2, "output": results[1]},
            "resulting_colony": {"type": resulting_colony, "output": final_result},
            "fano_line": f"{colony1} × {colony2} → {resulting_colony}",
        }

    async def parallel_forge_implementation(
        self,
        modules: list[dict[str, str]],
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Launch N forge agents in parallel for N independent modules.

        This demonstrates maximum parallelism for independent implementation tasks.

        Args:
            modules: List of module specifications [{"name": "...", "spec": "..."}, ...]
            context: Optional shared context

        Returns:
            Implementation results for all modules
        """
        logger.info(f"Launching {len(modules)} parallel Forge agents")

        # Create parallel forge tasks
        forge_tasks = []
        for module in modules:
            task_desc = f"Implement module {module['name']}: {module['spec']}"
            forge_tasks.append(
                self._execute_colony(
                    ColonyType.FORGE,
                    task_desc,
                    {**context, "module": module} if context else {"module": module},
                )
            )

        # Execute all forges in parallel
        forge_results = await asyncio.gather(*forge_tasks)

        # Integrate all modules with Nexus
        integration_result = await self._execute_colony(
            ColonyType.NEXUS,
            "Integrate all implemented modules",
            {"modules": forge_results},
        )

        # Verify with Crystal
        verification_result = await self._execute_colony(
            ColonyType.CRYSTAL,
            "Verify all module implementations and integration",
            {"modules": forge_results, "integration": integration_result},
        )

        return {
            "modules": {modules[i]["name"]: forge_results[i] for i in range(len(modules))},
            "integration": integration_result,
            "verification": verification_result,
        }

    async def debug_and_fix_workflow(
        self,
        error_description: str,
        codebase_context: dict[str, Any],
    ) -> dict[str, Any]:
        """Debug and fix workflow using Flow → Forge → Crystal.

        Demonstrates the debugging cycle with adaptation.

        Args:
            error_description: Description of the error
            codebase_context: Context about the codebase

        Returns:
            Fix results
        """
        logger.info(f"Starting debug and fix workflow for: {error_description}")

        # Flow: Diagnose the issue
        diagnosis = await self._execute_colony(
            ColonyType.FLOW,
            f"Diagnose error: {error_description}",
            codebase_context,
        )

        # Forge: Implement the fix
        fix = await self._execute_colony(
            ColonyType.FORGE,
            f"Implement fix based on diagnosis: {diagnosis}",
            {"diagnosis": diagnosis, **codebase_context},
        )

        # Crystal: Verify the fix
        verification = await self._execute_colony(
            ColonyType.CRYSTAL,
            "Verify fix resolves the issue and doesn't break anything",
            {"fix": fix, "original_error": error_description},
        )

        return {
            "diagnosis": diagnosis,
            "fix": fix,
            "verification": verification,
            "success": self._check_fix_success(verification),
        }

    async def research_driven_development(
        self,
        feature_request: str,
        constraints: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Research-driven development using Grove → Beacon → Forge → Crystal.

        Demonstrates how research informs architecture and implementation.

        Args:
            feature_request: Description of requested feature
            constraints: Optional constraints (performance, security, etc.)

        Returns:
            Development results
        """
        logger.info(f"Research-driven development for: {feature_request}")

        # Grove: Research existing solutions and patterns
        research = await self._execute_colony(
            ColonyType.GROVE,
            f"Research existing solutions for: {feature_request}",
            constraints,
        )

        # Beacon: Design architecture based on research
        architecture = await self._execute_colony(
            ColonyType.BEACON,
            "Design architecture based on research findings",
            {"research": research, "constraints": constraints},
        )

        # Forge: Implement based on architecture
        implementation = await self._execute_colony(
            ColonyType.FORGE,
            "Implement feature following architecture",
            {"architecture": architecture, "research": research},
        )

        # Crystal: Comprehensive verification
        verification = await self._execute_colony(
            ColonyType.CRYSTAL,
            "Verify implementation meets requirements and constraints",
            {
                "implementation": implementation,
                "architecture": architecture,
                "requirements": feature_request,
                "constraints": constraints,
            },
        )

        return {
            "research": research,
            "architecture": architecture,
            "implementation": implementation,
            "verification": verification,
        }

    # ========== Helper Methods ==========

    async def _execute_colony(
        self,
        colony_type: ColonyType,
        task: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a single colony agent.

        Args:
            colony_type: Which colony to execute
            task: Task description
            context: Optional context

        Returns:
            Colony output
        """
        logger.info(f"Executing {colony_type}: {task[:50]}...")

        # Get the colony agent
        self.colonies[colony_type]

        # Create input for the agent

        # Execute the agent (simulated here - in practice would call agent.execute())
        # For demonstration, we'll return a structured response
        result = {
            "colony": colony_type.value,
            "task": task,
            "output": f"{colony_type} completed: {task}",
            "confidence": 0.85 + torch.rand(1).item() * 0.15,
            "safety_score": 0.9 + torch.rand(1).item() * 0.1,
        }

        logger.info(f"{colony_type} complete (confidence: {result['confidence']:.2f})")
        return result

    def _synthesize_planning(self, planning_results: dict[str, Any]) -> str:
        """Synthesize planning outputs from Beacon, Grove, and Spark.

        Args:
            planning_results: Results from planning colonies

        Returns:
            Synthesized plan
        """
        beacon = planning_results["beacon"]["output"]
        grove = planning_results["grove"]["output"]
        spark = planning_results["spark"]["output"]

        synthesis = (
            f"Synthesized Plan:\n"
            f"- Architecture (Beacon): {beacon}\n"
            f"- Best Practices (Grove): {grove}\n"
            f"- Creative Approaches (Spark): {spark}"
        )

        return synthesis

    def _needs_integration(self, forge_result: dict[str, Any]) -> bool:
        """Check if Nexus integration is needed.

        Args:
            forge_result: Forge implementation result

        Returns:
            True if integration needed
        """
        # For demo, randomly decide (in practice, check for multiple components)
        return torch.rand(1).item() > 0.3

    def _needs_debugging(self, results: dict[str, Any]) -> bool:
        """Check if Flow debugging is needed.

        Args:
            results: Current results

        Returns:
            True if debugging needed
        """
        # For demo, check if any confidence is low
        for _key, value in results.items():
            if isinstance(value, dict) and "confidence" in value:
                if value["confidence"] < 0.7:
                    return True
        return False

    def _verify_safety(self, crystal_result: dict[str, Any]) -> dict[str, bool]:
        """Verify safety invariant h(x) ≥ 0.

        Args:
            crystal_result: Crystal verification result

        Returns:
            Safety check result
        """
        safety_score = crystal_result.get("safety_score", 0)
        return {
            "safe": safety_score >= 0.5,  # h(x) ≥ 0 threshold
            "score": safety_score,
            "reason": "All safety checks passed"
            if safety_score >= 0.5
            else "Safety threshold not met",
        }

    def _get_fano_composition(
        self,
        colony1: ColonyType,
        colony2: ColonyType,
    ) -> ColonyType:
        """Get resulting colony from Fano composition.

        Args:
            colony1: First colony
            colony2: Second colony

        Returns:
            Resulting colony type
        """
        # Fano plane composition rules
        fano_rules = {
            (ColonyType.SPARK, ColonyType.FORGE): ColonyType.FLOW,
            (ColonyType.SPARK, ColonyType.NEXUS): ColonyType.BEACON,
            (ColonyType.SPARK, ColonyType.GROVE): ColonyType.CRYSTAL,
            (ColonyType.FORGE, ColonyType.NEXUS): ColonyType.GROVE,
            (ColonyType.BEACON, ColonyType.FORGE): ColonyType.CRYSTAL,
            (ColonyType.NEXUS, ColonyType.FLOW): ColonyType.CRYSTAL,
            (ColonyType.BEACON, ColonyType.FLOW): ColonyType.GROVE,
        }

        # Check both orderings
        key = (colony1, colony2)
        if key in fano_rules:
            return fano_rules[key]

        key_reversed = (colony2, colony1)
        if key_reversed in fano_rules:
            return fano_rules[key_reversed]

        # Default to Crystal for verification
        return ColonyType.CRYSTAL

    def _check_fix_success(self, verification: dict[str, Any]) -> bool:
        """Check if a fix was successful.

        Args:
            verification: Crystal verification result

        Returns:
            True if fix successful
        """
        return verification.get("confidence", 0) > 0.8 and verification.get("safety_score", 0) > 0.9


async def main():
    """Run orchestration examples."""
    orchestrator = OrchestrationExample()

    # Example 1: Full PLAN-EXECUTE-VERIFY workflow
    print("\n" + "=" * 80)
    print("EXAMPLE 1: PLAN → EXECUTE → VERIFY Workflow")
    print("=" * 80)

    result1 = await orchestrator.plan_execute_verify_workflow(
        task="Build a real-time data processing pipeline",
        context={"requirements": ["low latency", "high throughput", "fault tolerance"]},
    )
    print(f"Workflow completed with {len(result1)} phases")

    # Example 2: Fano line composition
    print("\n" + "=" * 80)
    print("EXAMPLE 2: Fano Line Composition (Spark × Forge → Flow)")
    print("=" * 80)

    result2 = await orchestrator.fano_line_composition(
        colony1=ColonyType.SPARK,
        colony2=ColonyType.FORGE,
        task="Create an innovative caching solution",
        context={"constraints": ["memory efficient", "thread safe"]},
    )
    print(f"Fano composition: {result2['fano_line']}")

    # Example 3: Parallel Forge implementation
    print("\n" + "=" * 80)
    print("EXAMPLE 3: Parallel Forge Implementation")
    print("=" * 80)

    modules = [
        {"name": "auth_module", "spec": "JWT-based authentication"},
        {"name": "cache_module", "spec": "Redis-backed caching"},
        {"name": "api_module", "spec": "RESTful API endpoints"},
        {"name": "db_module", "spec": "PostgreSQL data layer"},
    ]

    result3 = await orchestrator.parallel_forge_implementation(
        modules=modules,
        context={"framework": "FastAPI", "python_version": "3.11"},
    )
    print(f"Implemented {len(result3['modules'])} modules in parallel")

    # Example 4: Debug and fix workflow
    print("\n" + "=" * 80)
    print("EXAMPLE 4: Debug and Fix Workflow")
    print("=" * 80)

    result4 = await orchestrator.debug_and_fix_workflow(
        error_description="Memory leak in world model training loop",
        codebase_context={
            "file": "kagami/core/world_model/kagami_world_model.py",
            "function": "train_step",
            "symptoms": ["increasing memory usage", "OOM after 1000 iterations"],
        },
    )
    print(f"Fix successful: {result4['success']}")

    # Example 5: Research-driven development
    print("\n" + "=" * 80)
    print("EXAMPLE 5: Research-Driven Development")
    print("=" * 80)

    result5 = await orchestrator.research_driven_development(
        feature_request="Implement quantum-inspired optimization for E8 lattice quantization",
        constraints={
            "performance": "must be faster than current implementation",
            "accuracy": "maintain 99% approximation quality",
            "memory": "no more than 2x current memory usage",
        },
    )
    print(
        f"Research-driven development completed with confidence: {result5['verification']['confidence']:.2f}"
    )

    print("\n" + "=" * 80)
    print("All orchestration examples completed successfully!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
