"""Centralized prompt management for Kagami.

This module is the SINGLE SOURCE OF TRUTH for all system prompts.
All prompt consumers (Python agents, Claude Code, Cursor rules) inherit from here.

Architecture:
- COLONY_PROMPTS: The seven colony system prompts (optimized, token-efficient)
- UNIVERSAL_CONTEXT: Shared context for all prompts
- SAFETY_LAYER: Security prelude for all LLM interactions
- get_agent_system_prompt(): Factory for complete agent prompts

Sync: Pre-commit hook regenerates .claude/agents/*.md from these definitions.
"""

from kagami.core.prompts.agent_system_prompts import (
    get_agent_system_prompt,
    get_claude_code_agent_markdown,
)
from kagami.core.prompts.colonies import (
    COLONY_PROMPTS,
    ColonyPrompt,
    get_colony_prompt,
)
from kagami.core.prompts.context import (
    SAFETY_LAYER,
    UNIVERSAL_CONTEXT,
    get_full_context,
)

__all__ = [
    "COLONY_PROMPTS",
    "SAFETY_LAYER",
    "UNIVERSAL_CONTEXT",
    "ColonyPrompt",
    "get_agent_system_prompt",
    "get_claude_code_agent_markdown",
    "get_colony_prompt",
    "get_full_context",
]
