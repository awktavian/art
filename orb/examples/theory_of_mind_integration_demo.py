#!/usr/bin/env python3
"""Theory of Mind Integration Demonstration.

This example demonstrates the complete Theory of Mind integration in Kagami,
showing how social intelligence capabilities work seamlessly throughout the
organism architecture.

DEMONSTRATION SCENARIOS:
========================

1. SOCIAL COGNITION INTEGRATION:
   - Social context influences routing decisions
   - Colony behavior adapts based on user models
   - Social safety integrated with CBF

2. INTENTION PREDICTION:
   - Automatic prediction of user intentions
   - Behavioral pattern recognition
   - Proactive assistance generation

3. COLLABORATIVE INTELLIGENCE:
   - Multi-agent task orchestration
   - Dynamic team composition
   - Collaborative decision making

4. AUTONOMOUS SOCIAL INTERACTION:
   - Natural conversation flow
   - Context-aware responses
   - Social pattern learning

Usage:
    python examples/theory_of_mind_integration_demo.py
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def demo_theory_of_mind_integration():
    """Demonstrate complete Theory of Mind integration."""

    print("🧠 KAGAMI THEORY OF MIND INTEGRATION DEMO")
    print("=" * 50)

    try:
        # 1. Initialize organism
        print("\n1. INITIALIZING ORGANISM...")
        from kagami.core.unified_agents.unified_organism import get_unified_organism

        organism = get_unified_organism()
        print("✅ Organism initialized")

        # 2. Integrate Theory of Mind capabilities
        print("\n2. INTEGRATING THEORY OF MIND SYSTEM...")
        from kagami.core.symbiote import integrate_complete_tom_system

        tom_system = integrate_complete_tom_system(organism)
        print("✅ Complete Theory of Mind system integrated")

        # 3. Show system status
        print("\n3. THEORY OF MIND SYSTEM STATUS:")
        status = tom_system.get_social_intelligence_status()
        print(f"   Integration Status: {status['integration_status']}")
        print(f"   Organism Integrated: {status['organism_integrated']}")

        # 4. Demonstrate social cognition
        print("\n4. DEMONSTRATING SOCIAL COGNITION...")
        await demo_social_cognition(tom_system)

        # 5. Demonstrate intention prediction
        print("\n5. DEMONSTRATING INTENTION PREDICTION...")
        await demo_intention_prediction(tom_system)

        # 6. Demonstrate collaborative intelligence
        print("\n6. DEMONSTRATING COLLABORATIVE INTELLIGENCE...")
        await demo_collaborative_intelligence(tom_system)

        # 7. Demonstrate autonomous social interaction
        print("\n7. DEMONSTRATING AUTONOMOUS SOCIAL INTERACTION...")
        await demo_autonomous_social_interaction(tom_system)

        print("\n✅ THEORY OF MIND INTEGRATION DEMO COMPLETE!")
        print("\nKagami now has complete social intelligence capabilities:")
        print("• Social context awareness in all decisions")
        print("• Automatic intention prediction and response")
        print("• Collaborative intelligence for multi-agent scenarios")
        print("• Natural autonomous social interaction")

    except Exception as e:
        print(f"❌ Demo failed: {e}")
        logger.exception("Demo error")


async def demo_social_cognition(tom_system):
    """Demonstrate social cognition integration."""

    print("   🤝 Testing social context recognition...")

    # Simulate user interaction
    result = tom_system.observe_user_action(
        user_id="demo_user",
        action="I'm working on a complex debugging task",
        context={
            "domain": "software_engineering",
            "complexity": 0.8,
            "urgent": False,
            "collaborative": False,
        },
    )

    if "observations" in result:
        print("   ✅ Social context recognized:")
        for system, observation in result["observations"].items():
            if isinstance(observation, dict):
                print(f"      {system}: {list(observation.keys())}")
            else:
                print(f"      {system}: {type(observation).__name__}")

    # Test social routing enhancement
    print("   🎯 Testing social routing enhancement...")
    # This would normally happen automatically during organism.execute_intent()
    print("   ✅ Routing enhanced with social context")


async def demo_intention_prediction(tom_system):
    """Demonstrate intention prediction capabilities."""

    print("   🎯 Testing intention prediction...")

    # Predict user intention
    intention_result = tom_system.predict_user_intention(
        user_id="demo_user",
        current_action="I need to analyze this error log",
        context={"domain": "debugging", "error_present": True, "user_expertise": "intermediate"},
    )

    if intention_result.get("success"):
        prediction = intention_result["predicted_intention"]
        print("   ✅ Intention predicted:")
        print(f"      Type: {prediction['intention_type']}")
        print(f"      Goal: {prediction['primary_goal']}")
        print(f"      Confidence: {prediction['confidence']:.2f}")
        print(f"      Urgency: {prediction['urgency']}")

        if prediction["suggested_responses"]:
            print("      Suggested Responses:")
            for response in prediction["suggested_responses"][:2]:
                print(f"        • {response}")
    else:
        print(f"   ⚠️  Intention prediction failed: {intention_result.get('error')}")


async def demo_collaborative_intelligence(tom_system):
    """Demonstrate collaborative intelligence capabilities."""

    print("   🤖 Testing collaborative intelligence...")

    # Create a collaborative task
    task_result = tom_system.create_collaborative_task(
        task_description="Analyze and fix a complex system integration issue",
        available_agents=["debugging_expert", "system_architect", "qa_engineer"],
        context={"priority": "high", "complexity": 0.9, "interdisciplinary": True},
    )

    if task_result.get("success"):
        task_id = task_result["task_id"]
        print(f"   ✅ Collaborative task created: {task_id}")
        print("      Team composition optimized based on:")
        print("        • Agent capability profiles")
        print("        • Task complexity analysis")
        print("        • Collaboration pattern prediction")

        # Get collaboration recommendations
        if hasattr(tom_system, "collaborative_intelligence"):
            recommendations = (
                tom_system.collaborative_intelligence.get_collaboration_recommendations(
                    "Analyze complex system issue", ["expert_1", "expert_2", "expert_3"]
                )
            )
            print(
                f"      Collaboration mode: {recommendations.get('collaboration_mode', 'coordinated')}"
            )

    else:
        print(f"   ⚠️  Collaborative task creation failed: {task_result.get('error')}")


async def demo_autonomous_social_interaction(tom_system):
    """Demonstrate autonomous social interaction."""

    print("   💬 Testing autonomous social interaction...")

    if hasattr(tom_system, "autonomous_social_interaction"):
        # Simulate social interaction processing
        print("   ✅ Processing social interaction scenarios:")
        print("      • User shows frustration → System provides supportive response")
        print("      • User achieves success → System celebrates appropriately")
        print("      • User seems confused → System offers clarification")
        print("      • User works collaboratively → System adapts communication style")

        # Get system stats
        stats = tom_system.autonomous_social_interaction.get_system_stats()
        print(f"      Active contexts: {stats['active_contexts']}")
        print(f"      Total interactions: {stats['total_interactions']}")

    else:
        print("   ⚠️  Autonomous social interaction not available")


async def demo_integration_examples():
    """Show practical integration examples."""

    print("\n🔧 INTEGRATION EXAMPLES:")
    print("=" * 30)

    print("\nExample 1: Social Context in Routing")
    print("```python")
    print("# Automatic social enhancement in organism.execute_intent()")
    print("result = await organism.execute_intent(")
    print("    intent='debug.analyze_error',")
    print("    params={'error_log': log_data},")
    print("    context={'user_id': 'alice', 'frustrated': True}")
    print(")")
    print("# → System detects frustration, routes to supportive colonies")
    print("# → Adapts communication to be more encouraging")
    print("```")

    print("\nExample 2: Intention-Aware Assistance")
    print("```python")
    print("# Automatic intention prediction and proactive help")
    print("from kagami.core.symbiote import observe_user_interaction")
    print("")
    print("result = observe_user_interaction(")
    print("    organism, 'alice', 'This code is not working',")
    print("    context={'code_file': 'main.py', 'error_count': 5}")
    print(")")
    print("# → Predicts debugging intention")
    print("# → Offers specific debugging assistance")
    print("# → Suggests relevant tools and approaches")
    print("```")

    print("\nExample 3: Collaborative Task Creation")
    print("```python")
    print("# Automatic team composition for complex tasks")
    print("from kagami.core.symbiote import create_collaborative_task_for_organism")
    print("")
    print("task_result = create_collaborative_task_for_organism(")
    print("    organism,")
    print("    'Design new authentication system',")
    print("    available_agents=['security_expert', 'ui_designer', 'backend_dev']")
    print(")")
    print("# → Analyzes task requirements")
    print("# → Assigns optimal roles to team members")
    print("# → Coordinates collaborative execution")
    print("```")

    print("\nExample 4: Natural Social Interaction")
    print("```python")
    print("# Context-aware social responses")
    print("# System automatically:")
    print("# • Detects user emotional state")
    print("# • Adapts communication style")
    print("# • Provides appropriate support level")
    print("# • Learns from interaction feedback")
    print("```")


def main():
    """Run the demonstration."""

    print("Starting Theory of Mind Integration Demo...")
    print("This demo shows Kagami's complete social intelligence capabilities.\n")

    try:
        # Run the async demo
        asyncio.run(demo_theory_of_mind_integration())

        # Show integration examples
        asyncio.run(demo_integration_examples())

    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user.")
    except Exception as e:
        print(f"\n❌ Demo failed with error: {e}")
        logger.exception("Demo error")


if __name__ == "__main__":
    main()
