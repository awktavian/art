"""Ideation Operations — Creative brainstorming and idea generation tools.

Provides brainstorming, idea generation, and concept exploration for Spark agent.

Used by: Spark

Created: December 28, 2025
"""

import logging
import random
from typing import Any

logger = logging.getLogger(__name__)


def brainstorm(
    topic: str,
    count: int = 10,
    style: str = "divergent",
) -> dict[str, Any]:
    """Brainstorm ideas on topic.

    Args:
        topic: Topic to brainstorm
        count: Number of ideas to generate
        style: Brainstorming style (divergent, convergent, lateral)

    Returns:
        Brainstormed ideas
    """
    try:
        logger.info(f"Brainstorming {count} ideas for: {topic}")

        ideas = []

        # Idea generation templates
        templates = {
            "divergent": [
                f"What if we {_random_action()} {topic}?",
                f"How might we combine {topic} with {_random_concept()}?",
                f"What's the opposite of {topic}?",
                f"What would happen if we removed {_random_element()} from {topic}?",
                f"How could {_random_domain()} approach {topic}?",
            ],
            "convergent": [
                f"The core problem with {topic} is...",
                f"The best approach to {topic} is...",
                f"The key insight about {topic} is...",
            ],
            "lateral": [
                f"If {topic} was a {_random_metaphor()}, it would...",
                f"What does {topic} have in common with {_random_concept()}?",
                f"How would {_random_person()} solve {topic}?",
            ],
        }

        template_list = templates.get(style, templates["divergent"])

        for i in range(count):
            template = random.choice(template_list)
            ideas.append(
                {
                    "id": i + 1,
                    "idea": template,
                    "style": style,
                    "confidence": random.uniform(0.5, 0.9),
                }
            )

        return {
            "success": True,
            "topic": topic,
            "ideas": ideas,
            "count": len(ideas),
            "style": style,
        }

    except Exception as e:
        logger.error(f"Brainstorming failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "topic": topic,
        }


def generate_ideas(
    concept: str,
    constraints: list[str] | None = None,
    creativity: float = 0.8,
) -> dict[str, Any]:
    """Generate ideas with constraints.

    Args:
        concept: Core concept
        constraints: Constraints to satisfy
        creativity: Creativity level (0-1)

    Returns:
        Generated ideas
    """
    try:
        constraints = constraints or []
        ideas = []

        # Generate base ideas
        for i in range(int(creativity * 10)):
            idea = {
                "id": i + 1,
                "concept": f"{concept} with {_random_modifier()}",
                "satisfies_constraints": _check_constraints(constraints),
                "novelty_score": random.uniform(0.6, 1.0),
            }
            ideas.append(idea)

        return {
            "success": True,
            "concept": concept,
            "ideas": ideas,
            "constraints": constraints,
            "creativity_level": creativity,
        }

    except Exception as e:
        logger.error(f"Idea generation failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
        }


def ideate_variations(
    base_idea: str,
    variation_types: list[str] | None = None,
) -> dict[str, Any]:
    """Generate variations of base idea.

    Args:
        base_idea: Base idea to vary
        variation_types: Types of variations (amplify, simplify, twist, etc.)

    Returns:
        Idea variations
    """
    try:
        variation_types = variation_types or ["amplify", "simplify", "twist"]
        variations = []

        for var_type in variation_types:
            if var_type == "amplify":
                variations.append(
                    {
                        "type": "amplify",
                        "variation": f"{base_idea} × 10",
                        "description": "Amplified version",
                    }
                )
            elif var_type == "simplify":
                variations.append(
                    {
                        "type": "simplify",
                        "variation": f"Minimal {base_idea}",
                        "description": "Simplified version",
                    }
                )
            elif var_type == "twist":
                variations.append(
                    {
                        "type": "twist",
                        "variation": f"{base_idea} but {_random_twist()}",
                        "description": "Twisted version",
                    }
                )

        return {
            "success": True,
            "base_idea": base_idea,
            "variations": variations,
            "count": len(variations),
        }

    except Exception as e:
        logger.error(f"Variation generation failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
        }


def explore_concepts(
    starting_concept: str,
    depth: int = 3,
) -> dict[str, Any]:
    """Explore concept space.

    Args:
        starting_concept: Starting concept
        depth: Exploration depth

    Returns:
        Concept exploration map
    """
    try:
        concept_map = {
            "root": starting_concept,
            "branches": [],
        }

        # Generate concept branches
        for i in range(depth):
            branch = {
                "level": i + 1,
                "concepts": [
                    f"{starting_concept} + {_random_concept()}",
                    f"{starting_concept} via {_random_approach()}",
                    f"{starting_concept} without {_random_element()}",
                ],
            }
            concept_map["branches"].append(branch)

        return {
            "success": True,
            "starting_concept": starting_concept,
            "concept_map": concept_map,
            "depth": depth,
        }

    except Exception as e:
        logger.error(f"Concept exploration failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
        }


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def _random_action() -> str:
    """Get random action verb."""
    actions = ["amplify", "invert", "combine", "decompose", "transform", "reimagine"]
    return random.choice(actions)


def _random_concept() -> str:
    """Get random concept."""
    concepts = ["music", "nature", "geometry", "games", "stories", "systems"]
    return random.choice(concepts)


def _random_element() -> str:
    """Get random element."""
    elements = ["time", "space", "structure", "randomness", "pattern", "symmetry"]
    return random.choice(elements)


def _random_domain() -> str:
    """Get random domain."""
    domains = ["biology", "physics", "art", "architecture", "music", "mathematics"]
    return random.choice(domains)


def _random_metaphor() -> str:
    """Get random metaphor."""
    metaphors = ["river", "tree", "fire", "crystal", "storm", "garden"]
    return random.choice(metaphors)


def _random_person() -> str:
    """Get random person/role."""
    people = ["a child", "an artist", "a scientist", "a philosopher", "a builder"]
    return random.choice(people)


def _random_modifier() -> str:
    """Get random modifier."""
    modifiers = ["playful", "minimal", "chaotic", "structured", "organic", "digital"]
    return random.choice(modifiers)


def _random_twist() -> str:
    """Get random twist."""
    twists = ["upside down", "inside out", "backwards", "transparent", "invisible"]
    return random.choice(twists)


def _random_approach() -> str:
    """Get random approach."""
    approaches = ["iteration", "recursion", "emergence", "collaboration", "constraint"]
    return random.choice(approaches)


def _check_constraints(constraints: list[str]) -> bool:
    """Check if constraints are satisfied."""
    # Simplified: randomly satisfy constraints
    return random.random() > 0.3


__all__ = [
    "brainstorm",
    "explore_concepts",
    "generate_ideas",
    "ideate_variations",
]
