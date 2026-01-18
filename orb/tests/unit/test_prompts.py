"""Tests for centralized prompt system."""

import pytest


class TestColonyPrompts:
    """Test the canonical colony prompts."""

    def test_all_colonies_exist(self):
        """All seven colonies must have prompts."""
        from kagami.core.prompts.colonies import COLONY_PROMPTS

        expected = ["spark", "forge", "flow", "nexus", "beacon", "grove", "crystal"]
        for name in expected:
            assert name in COLONY_PROMPTS, f"Missing colony: {name}"

    def test_prompt_structure(self):
        """Each prompt must have required fields."""
        from kagami.core.prompts.colonies import COLONY_PROMPTS

        for name, prompt in COLONY_PROMPTS.items():
            assert prompt.name == name
            assert prompt.emoji, f"{name} missing emoji"
            assert prompt.title, f"{name} missing title"
            assert prompt.system_prompt, f"{name} missing system_prompt"
            assert prompt.cursor_rule, f"{name} missing cursor_rule"
            assert prompt.tools, f"{name} missing tools"
            assert prompt.keywords, f"{name} missing keywords"

    def test_prompt_quality(self):
        """Prompts must contain quality markers."""
        from kagami.core.prompts.colonies import COLONY_PROMPTS

        for name, prompt in COLONY_PROMPTS.items():
            text = prompt.system_prompt
            # Must have header with name
            assert f"# {prompt.emoji}" in text, f"{name} missing header"
            # Must have psychology table
            has_psychology = "**Want**" in text and "**Gift**" in text
            assert has_psychology, f"{name} missing psychology table"
            # Must have math
            assert "V(x)" in text or "geometry" in text, f"{name} missing math"

    def test_prompt_token_efficiency(self):
        """Prompts should be reasonably lean."""
        from kagami.core.prompts.colonies import COLONY_PROMPTS

        # 2000 chars ~= ~500 tokens (rough estimate)
        # Prompts include service context (Composio) so need more room
        for name, prompt in COLONY_PROMPTS.items():
            assert len(prompt.system_prompt) < 2000, (
                f"{name} prompt too long ({len(prompt.system_prompt)})"
            )

    def test_cursor_rule_has_frontmatter(self):
        """Cursor rules must have YAML frontmatter."""
        from kagami.core.prompts.colonies import COLONY_PROMPTS

        for name, prompt in COLONY_PROMPTS.items():
            assert prompt.cursor_rule.startswith("---"), f"{name} missing frontmatter"
            assert "description:" in prompt.cursor_rule, f"{name} missing description"


class TestAgentSystemPrompts:
    """Test the agent system prompt factory."""

    def test_get_agent_system_prompt_colony(self):
        """Factory should return full prompt for colonies."""
        from kagami.core.prompts import get_agent_system_prompt

        for name in ["spark", "forge", "flow"]:
            result = get_agent_system_prompt(name)
            assert "CAPABILITIES:" in result  # Universal context
            assert "You are" in result or "I " in result

    def test_get_agent_system_prompt_kagami(self):
        """Factory should return Kagami orchestrator prompt."""
        from kagami.core.prompts import get_agent_system_prompt

        result = get_agent_system_prompt("kagami")
        assert "Spark" in result
        assert "Forge" in result


class TestClaudeCodeGeneration:
    """Test Claude Code agent markdown generation."""

    def test_generate_all_agents(self):
        """Should generate markdown for all agents."""
        from kagami.core.prompts.agent_system_prompts import generate_all_claude_code_agents

        agents = generate_all_claude_code_agents()

        assert "kagami.md" in agents
        assert "spark.md" in agents
        assert len(agents) == 8  # kagami + 7 colonies

    def test_markdown_format(self):
        """Generated markdown should have header."""
        from kagami.core.prompts import get_claude_code_agent_markdown

        for name in ["spark", "forge"]:
            md = get_claude_code_agent_markdown(name)
            assert md.startswith("#"), f"{name} missing header"
            assert "Generated from" in md


class TestPythonAgentsUseCanonical:
    """Verify Python agents import from canonical source."""

    def test_spark_agent_uses_canonical(self):
        """SparkAgent should use canonical prompt."""
        from kagami.core.unified_agents.agents.spark_agent import SparkAgent
        from kagami.core.prompts.colonies import SPARK

        agent = SparkAgent()
        assert agent.get_system_prompt() == SPARK.system_prompt


class TestPromptSync:
    """Test the prompt sync mechanism."""

    def test_sync_script_exists(self):
        """Sync script should exist."""
        from pathlib import Path

        script = Path("scripts/hooks/sync-prompts.py")
        assert script.exists()

    def test_precommit_has_sync_hook(self):
        """Pre-commit config should include sync hook."""
        from pathlib import Path

        config = Path(".pre-commit-config.yaml").read_text()
        assert "sync-prompts" in config
