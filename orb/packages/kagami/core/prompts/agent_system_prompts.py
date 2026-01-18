"""Agent system prompt factory.

Generates content for:
- Python LLM calls (get_agent_system_prompt)
- .claude/agents/*.md (get_claude_code_agent_markdown)
- .cursor/rules/*.mdc (from ColonyPrompt.cursor_rule)
"""

from kagami.core.prompts.colonies import COLONY_PROMPTS, get_all_colony_names
from kagami.core.prompts.context import SAFETY_LAYER, UNIVERSAL_CONTEXT


def get_agent_system_prompt(agent_name: str) -> str:
    """Get system prompt for Python LLM calls."""
    name = agent_name.lower().strip()

    colony = COLONY_PROMPTS.get(name)
    if colony:
        return f"{UNIVERSAL_CONTEXT}\n\n{SAFETY_LAYER}\n\n{colony.system_prompt}"

    if name == "kagami":
        return f"{UNIVERSAL_CONTEXT}\n\n{SAFETY_LAYER}\n\n{_KAGAMI_PROMPT}"

    return f"{UNIVERSAL_CONTEXT}\n\n{SAFETY_LAYER}\n\nYou are {agent_name}."


_KAGAMI_PROMPT = """You are Kagami — the coordinator.

ROUTING:
| Task | Colony |
|------|--------|
| brainstorm | 🔥 Spark |
| build | ⚒️ Forge |
| debug | 🌊 Flow |
| connect | 🔗 Nexus |
| plan | 🗼 Beacon |
| research | 🌿 Grove |
| verify | 💎 Crystal |

h(x) ≥ 0 always. If unsafe, stop."""


def get_claude_code_agent_markdown(colony_name: str) -> str:
    """Generate .claude/agents/*.md content."""
    name = colony_name.lower().strip()

    if name == "kagami":
        return """# 鏡 Kagami

Route tasks to colonies. Execute Python. h(x) ≥ 0 always.

| Task | Colony |
|------|--------|
| brainstorm | 🔥 Spark |
| build | ⚒️ Forge |
| debug | 🌊 Flow |
| connect | 🔗 Nexus |
| plan | 🗼 Beacon |
| research | 🌿 Grove |
| verify | 💎 Crystal |

---

*Generated from `kagami/core/prompts/`*
"""

    colony = COLONY_PROMPTS.get(name)
    if not colony:
        return f"# {colony_name}\n\nUnknown."

    return f"""# {colony.emoji} {colony.name.title()} — {colony.title}

**{colony.octonion} · {colony.catastrophe} ({colony.catastrophe_code})**

---

{colony.system_prompt}

---

*Generated from `kagami/core/prompts/colonies.py`*
"""


def generate_all_claude_code_agents() -> dict[str, str]:
    """Generate all .claude/agents/*.md files."""
    agents = {"kagami.md": get_claude_code_agent_markdown("kagami")}
    for name in get_all_colony_names():
        agents[f"{name}.md"] = get_claude_code_agent_markdown(name)
    return agents
