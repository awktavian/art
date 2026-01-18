"""Markdown Agent Loader — Parse markdown files into live agents.

This module:
1. Parses markdown files with YAML front matter
2. Validates against the AgentSchema
3. Creates AgentState runtime objects
4. Manages agent registry and lifecycle

Protocol:
    .md file → parse → validate → AgentState → runtime

Directory Structure:
    _agents/
        spark.md
        forge.md
        obs-studio.md
    _crafts/
        mop.md
        craft.md

Colony: Nexus (e4) — Integration
Created: January 7, 2026
鏡
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from kagami.core.agents.schema import (
    AgentState,
    validate_agent_schema,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Front matter regex: matches YAML between --- markers
FRONT_MATTER_REGEX = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


# =============================================================================
# Markdown Parsing
# =============================================================================


@dataclass
class ParsedMarkdown:
    """Result of parsing a markdown file.

    Attributes:
        front_matter: Parsed YAML front matter.
        content: Markdown content after front matter.
        raw: Original raw file content.
        path: Source file path.
    """

    front_matter: dict[str, Any]
    content: str
    raw: str
    path: Path | None = None


def parse_markdown(text: str, path: Path | None = None) -> ParsedMarkdown:
    """Parse markdown file with YAML front matter.

    Args:
        text: Raw markdown text.
        path: Optional source file path.

    Returns:
        ParsedMarkdown with front matter and content.

    Example:
        ```python
        md = '''---
        i_am:
          id: my-agent
          name: My Agent
        ---
        # Hello World
        '''
        parsed = parse_markdown(md)
        assert parsed.front_matter["i_am"]["id"] == "my-agent"
        ```
    """
    match = FRONT_MATTER_REGEX.match(text)

    if match:
        yaml_text = match.group(1)
        content = text[match.end() :]

        try:
            front_matter = yaml.safe_load(yaml_text) or {}
        except yaml.YAMLError as e:
            logger.error(f"YAML parse error: {e}")
            front_matter = {}
    else:
        front_matter = {}
        content = text

    return ParsedMarkdown(
        front_matter=front_matter,
        content=content.strip(),
        raw=text,
        path=path,
    )


def parse_markdown_file(path: Path | str) -> ParsedMarkdown:
    """Parse markdown file from filesystem.

    Args:
        path: Path to markdown file.

    Returns:
        ParsedMarkdown with front matter and content.
    """
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    return parse_markdown(text, path=path)


# =============================================================================
# Agent Loading
# =============================================================================


def load_agent(path: Path | str) -> AgentState:
    """Load agent from markdown file.

    Args:
        path: Path to agent markdown file.

    Returns:
        AgentState ready for runtime.

    Raises:
        ValueError: If agent schema is invalid.
    """
    parsed = parse_markdown_file(path)

    # Validate schema
    front_matter = parsed.front_matter.copy()
    front_matter["content"] = parsed.content

    try:
        schema = validate_agent_schema(front_matter)
    except Exception as e:
        raise ValueError(f"Invalid agent schema in {path}: {e}") from e

    # Create runtime state
    return AgentState(
        agent_id=schema.i_am.id,
        schema=schema,
        last_interaction=time.time(),
    )


def load_agent_from_text(text: str, agent_id: str | None = None) -> AgentState:
    """Load agent from markdown text.

    Args:
        text: Markdown text with YAML front matter.
        agent_id: Override agent ID (optional).

    Returns:
        AgentState ready for runtime.
    """
    parsed = parse_markdown(text)

    front_matter = parsed.front_matter.copy()
    front_matter["content"] = parsed.content

    # Handle missing i_am section
    if "i_am" not in front_matter:
        front_matter["i_am"] = {"id": agent_id or "unnamed", "name": "Unnamed Agent"}
    elif agent_id:
        front_matter["i_am"]["id"] = agent_id

    schema = validate_agent_schema(front_matter)

    return AgentState(
        agent_id=schema.i_am.id,
        schema=schema,
        last_interaction=time.time(),
    )


# =============================================================================
# Agent Registry
# =============================================================================


@dataclass
class AgentRegistry:
    """Registry of loaded agents.

    Manages agent lifecycle:
    - Loading from filesystem
    - Hot reloading on file changes
    - State persistence
    - Garbage collection

    Attributes:
        agents: Map of agent_id to AgentState.
        paths: Map of agent_id to source path.
        _lock: Async lock for concurrent access.
    """

    agents: dict[str, AgentState] = field(default_factory=dict)
    paths: dict[str, Path] = field(default_factory=dict)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def load_directory(self, directory: Path | str, pattern: str = "*.md") -> list[str]:
        """Load all agents from a directory.

        Args:
            directory: Directory containing agent markdown files.
            pattern: Glob pattern for agent files.

        Returns:
            List of loaded agent IDs.
        """
        directory = Path(directory)
        loaded = []

        async with self._lock:
            for path in directory.glob(pattern):
                try:
                    agent = load_agent(path)
                    self.agents[agent.agent_id] = agent
                    self.paths[agent.agent_id] = path
                    loaded.append(agent.agent_id)
                    logger.info(f"Loaded agent: {agent.agent_id} from {path}")
                except Exception as e:
                    logger.error(f"Failed to load agent from {path}: {e}")

        return loaded

    async def load_agent(self, path: Path | str) -> AgentState:
        """Load single agent from file.

        Args:
            path: Path to agent markdown file.

        Returns:
            Loaded AgentState.
        """
        path = Path(path)
        agent = load_agent(path)

        async with self._lock:
            self.agents[agent.agent_id] = agent
            self.paths[agent.agent_id] = path

        logger.info(f"Loaded agent: {agent.agent_id}")
        return agent

    async def reload_agent(self, agent_id: str) -> AgentState | None:
        """Reload agent from its source file.

        Args:
            agent_id: Agent to reload.

        Returns:
            Reloaded AgentState or None if not found.
        """
        async with self._lock:
            path = self.paths.get(agent_id)
            if not path:
                logger.warning(f"No source path for agent: {agent_id}")
                return None

            try:
                # Preserve runtime state
                old_state = self.agents.get(agent_id)
                new_agent = load_agent(path)

                if old_state:
                    new_agent.memory = old_state.memory
                    new_agent.secrets_found = old_state.secrets_found
                    new_agent.engagement = old_state.engagement

                self.agents[agent_id] = new_agent
                logger.info(f"Reloaded agent: {agent_id}")
                return new_agent

            except Exception as e:
                logger.error(f"Failed to reload agent {agent_id}: {e}")
                return None

    async def unload_agent(self, agent_id: str) -> bool:
        """Unload agent from registry.

        Args:
            agent_id: Agent to unload.

        Returns:
            True if agent was unloaded.
        """
        async with self._lock:
            if agent_id in self.agents:
                del self.agents[agent_id]
                self.paths.pop(agent_id, None)
                logger.info(f"Unloaded agent: {agent_id}")
                return True
            return False

    def get_agent(self, agent_id: str) -> AgentState | None:
        """Get agent by ID.

        Args:
            agent_id: Agent identifier.

        Returns:
            AgentState or None.
        """
        return self.agents.get(agent_id)

    def list_agents(self) -> list[str]:
        """List all loaded agent IDs."""
        return list(self.agents.keys())

    def get_agents_by_colony(self, colony: str) -> list[AgentState]:
        """Get all agents in a colony.

        Args:
            colony: Colony name (spark, forge, etc.).

        Returns:
            List of agents in the colony.
        """
        return [a for a in self.agents.values() if a.schema.i_am.colony.value == colony]


# =============================================================================
# File Watcher for Hot Reload
# =============================================================================


@dataclass
class AgentWatcher:
    """Watches agent files for changes and triggers reload.

    Uses polling for simplicity (works on all platforms).
    """

    registry: AgentRegistry
    interval: float = 2.0
    _running: bool = False
    _task: asyncio.Task | None = None
    _mtimes: dict[Path, float] = field(default_factory=dict)

    async def start(self) -> None:
        """Start watching for file changes."""
        if self._running:
            return

        self._running = True

        # Initialize mtimes
        for path in self.registry.paths.values():
            if path.exists():
                self._mtimes[path] = path.stat().st_mtime

        self._task = asyncio.create_task(self._watch_loop())
        logger.info("Agent watcher started")

    async def stop(self) -> None:
        """Stop watching for file changes."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Agent watcher stopped")

    async def _watch_loop(self) -> None:
        """Main watch loop."""
        while self._running:
            await asyncio.sleep(self.interval)
            await self._check_changes()

    async def _check_changes(self) -> None:
        """Check for file changes and reload."""
        for agent_id, path in list(self.registry.paths.items()):
            if not path.exists():
                continue

            current_mtime = path.stat().st_mtime
            last_mtime = self._mtimes.get(path, 0)

            if current_mtime > last_mtime:
                logger.info(f"Detected change in {path}")
                self._mtimes[path] = current_mtime
                await self.registry.reload_agent(agent_id)


# =============================================================================
# Singleton Registry
# =============================================================================


_registry: AgentRegistry | None = None
_watcher: AgentWatcher | None = None


def get_agent_registry() -> AgentRegistry:
    """Get the singleton agent registry."""
    global _registry
    if _registry is None:
        _registry = AgentRegistry()
    return _registry


def get_agent_watcher() -> AgentWatcher:
    """Get the singleton agent watcher."""
    global _watcher
    if _watcher is None:
        _watcher = AgentWatcher(registry=get_agent_registry())
    return _watcher


async def initialize_agents(
    directories: list[Path | str] | None = None,
    watch: bool = False,
) -> AgentRegistry:
    """Initialize agent system.

    Args:
        directories: Directories to load agents from.
        watch: Whether to watch for file changes.

    Returns:
        Initialized registry.
    """
    registry = get_agent_registry()

    # Default directories
    if directories is None:
        base = Path(__file__).parent.parent.parent.parent.parent / "apps" / "agents"
        directories = [base] if base.exists() else []

    # Load from directories
    for directory in directories:
        directory = Path(directory)
        if directory.exists():
            await registry.load_directory(directory)

    # Start watcher if requested
    if watch:
        watcher = get_agent_watcher()
        await watcher.start()

    return registry


# =============================================================================
# CLI Support
# =============================================================================


async def load_agents_cli(paths: list[str], watch: bool = False) -> None:
    """CLI entry point for loading agents.

    Args:
        paths: Paths to agent files or directories.
        watch: Whether to watch for changes.
    """
    registry = get_agent_registry()

    for path_str in paths:
        path = Path(path_str)

        if path.is_dir():
            loaded = await registry.load_directory(path)
            print(f"Loaded {len(loaded)} agents from {path}")
        elif path.is_file():
            agent = await registry.load_agent(path)
            print(f"Loaded agent: {agent.agent_id}")
        else:
            print(f"Path not found: {path}")

    if watch:
        print("Watching for changes... (Ctrl+C to stop)")
        watcher = get_agent_watcher()
        await watcher.start()

        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            await watcher.stop()


# =============================================================================
# Exports
# =============================================================================


__all__ = [
    # Registry
    "AgentRegistry",
    # Watcher
    "AgentWatcher",
    # Parsing
    "ParsedMarkdown",
    "get_agent_registry",
    "get_agent_watcher",
    # Initialization
    "initialize_agents",
    # Loading
    "load_agent",
    "load_agent_from_text",
    "load_agents_cli",
    "parse_markdown",
    "parse_markdown_file",
]
