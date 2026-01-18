"""HTML Agent Framework — #de_memo Cognitive Agents.

Implements HTML files as cognitive agents that:
- Self-identify via #de_memo metadata tags
- Declare capabilities for routing
- Participate in Byzantine consensus
- Connect to backend via mDNS discovery
- Store/retrieve state from content-addressed blobs

Architecture:
```
┌─────────────────────────────────────────────────────────────────────┐
│                      HTML AGENT STRUCTURE                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   <!DOCTYPE html>                                                    │
│   <html>                                                             │
│   <head>                                                             │
│       <!-- #de_memo metadata -->                                     │
│       <meta name="kagami:agent" content="true">                      │
│       <meta name="kagami:capabilities" content="...">               │
│       <meta name="kagami:colony" content="nexus">                   │
│       <meta name="kagami:version" content="1.0.0">                  │
│       <meta name="kagami:consensus-weight" content="1">             │
│   </head>                                                            │
│   <body>                                                             │
│       <!-- High-craft visual content -->                             │
│       ...                                                            │
│       <script type="module">                                         │
│           // Agent framework connection                              │
│           import { KagamiAgent } from './kagami-agent.js';          │
│           const agent = new KagamiAgent();                          │
│           await agent.connect();                                     │
│       </script>                                                      │
│   </body>                                                            │
│   </html>                                                            │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

Colony: Nexus (A₅) — The Bridge
h(x) ≥ 0. Always.

Created: January 2026
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# Enums and Types
# =============================================================================


class AgentStatus(Enum):
    """Agent operational status."""

    UNKNOWN = auto()
    INITIALIZING = auto()
    ACTIVE = auto()
    CONNECTED = auto()
    VOTING = auto()
    SUSPENDED = auto()
    ERROR = auto()


class AgentCapability(Enum):
    """Standard agent capabilities."""

    # Core capabilities
    DISPLAY = "display"  # Can render visual content
    INTERACT = "interact"  # Can handle user interaction
    COMPUTE = "compute"  # Can perform computations
    STORE = "store"  # Can store/retrieve data

    # Consensus capabilities
    VOTE = "vote"  # Can participate in voting
    PROPOSE = "propose"  # Can propose consensus items
    AUDIT = "audit"  # Can verify/audit state

    # Domain capabilities
    SMARTHOME = "smarthome"  # Smart home control
    COMPOSIO = "composio"  # Digital services
    BROWSER = "browser"  # Web automation
    EDUCATION = "education"  # Learning/teaching

    # Colony alignment
    SPARK = "spark"  # Creative/ideation
    FORGE = "forge"  # Building/implementation
    FLOW = "flow"  # Debugging/recovery
    NEXUS = "nexus"  # Integration/connection
    BEACON = "beacon"  # Planning/architecture
    GROVE = "grove"  # Research/learning
    CRYSTAL = "crystal"  # Verification/testing


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class AgentConfig:
    """Configuration for HTML agent framework.

    Attributes:
        agent_directory: Directory containing HTML agents.
        scan_interval: Interval between agent scans (seconds).
        mdns_service_type: mDNS service type for discovery.
        consensus_timeout: Timeout for consensus operations.
        max_agents: Maximum number of registered agents.
    """

    agent_directory: str = ""
    scan_interval: float = 30.0
    mdns_service_type: str = "_kagami-hub._tcp.local."
    consensus_timeout: float = 30.0
    max_agents: int = 100

    def __post_init__(self) -> None:
        """Load from environment."""
        if not self.agent_directory:
            self.agent_directory = os.environ.get(
                "KAGAMI_AGENT_DIRECTORY", str(Path.home() / ".kagami" / "agents")
            )

        self.scan_interval = float(
            os.environ.get("KAGAMI_AGENT_SCAN_INTERVAL", str(self.scan_interval))
        )


@dataclass
class AgentMetadata:
    """Metadata extracted from HTML agent file.

    Attributes:
        agent_id: Unique agent identifier (hash of content).
        file_path: Path to HTML file.
        name: Human-readable name.
        version: Semantic version.
        colony: Primary colony alignment.
        capabilities: Set of capabilities.
        consensus_weight: Weight in consensus voting.
        description: Agent description.
        created_at: Creation timestamp.
        updated_at: Last update timestamp.
        voice_stability: ElevenLabs stability parameter (0.0-1.0).
        voice_similarity_boost: ElevenLabs similarity boost (0.0-1.0).
        voice_style: ElevenLabs style parameter (0.0-1.0).
        voice_speed: ElevenLabs speed multiplier (0.5-2.0).
        personality_prompt: Voice personality/system prompt for TTS.
    """

    agent_id: str
    file_path: str
    name: str = "unnamed-agent"
    version: str = "1.0.0"
    colony: str = "nexus"
    capabilities: set[AgentCapability] = field(default_factory=set)
    consensus_weight: int = 1
    description: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    # Voice settings (ElevenLabs parameters)
    voice_stability: float = 0.45
    voice_similarity_boost: float = 0.78
    voice_style: float = 0.32
    voice_speed: float = 1.0
    personality_prompt: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "agent_id": self.agent_id,
            "file_path": self.file_path,
            "name": self.name,
            "version": self.version,
            "colony": self.colony,
            "capabilities": [c.value for c in self.capabilities],
            "consensus_weight": self.consensus_weight,
            "description": self.description,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            # Voice settings
            "voice_stability": self.voice_stability,
            "voice_similarity_boost": self.voice_similarity_boost,
            "voice_style": self.voice_style,
            "voice_speed": self.voice_speed,
            "personality_prompt": self.personality_prompt,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentMetadata:
        """Deserialize from dictionary."""
        capabilities = {AgentCapability(c) for c in data.get("capabilities", [])}
        return cls(
            agent_id=data["agent_id"],
            file_path=data["file_path"],
            name=data.get("name", "unnamed-agent"),
            version=data.get("version", "1.0.0"),
            colony=data.get("colony", "nexus"),
            capabilities=capabilities,
            consensus_weight=data.get("consensus_weight", 1),
            description=data.get("description", ""),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            # Voice settings
            voice_stability=data.get("voice_stability", 0.45),
            voice_similarity_boost=data.get("voice_similarity_boost", 0.78),
            voice_style=data.get("voice_style", 0.32),
            voice_speed=data.get("voice_speed", 1.0),
            personality_prompt=data.get("personality_prompt", ""),
        )


# =============================================================================
# HTML Agent
# =============================================================================


class HTMLAgent:
    """Represents a single HTML agent.

    Wraps an HTML file that follows the #de_memo convention,
    providing methods to extract metadata, participate in
    consensus, and communicate with the backend.

    Example:
        >>> agent = HTMLAgent("/path/to/agent.html")
        >>> await agent.load()
        >>> print(agent.metadata.capabilities)
        >>> await agent.vote(proposal_id, "approve")
    """

    def __init__(self, file_path: str | Path) -> None:
        """Initialize agent from HTML file.

        Args:
            file_path: Path to HTML file.
        """
        self.file_path = Path(file_path)
        self.metadata: AgentMetadata | None = None
        self.status = AgentStatus.UNKNOWN
        self._content: str = ""
        self._content_hash: str = ""
        self._last_loaded: float = 0

    async def load(self) -> bool:
        """Load and parse the HTML file.

        Returns:
            True if agent is valid and loaded.
        """
        try:
            self.status = AgentStatus.INITIALIZING

            if not self.file_path.exists():
                logger.warning(f"Agent file not found: {self.file_path}")
                self.status = AgentStatus.ERROR
                return False

            # Read content
            self._content = self.file_path.read_text(encoding="utf-8")
            self._content_hash = hashlib.sha256(self._content.encode()).hexdigest()
            self._last_loaded = time.time()

            # Extract metadata
            self.metadata = self._extract_metadata()

            if self.metadata:
                self.status = AgentStatus.ACTIVE
                logger.debug(f"Loaded agent: {self.metadata.name}")
                return True
            else:
                self.status = AgentStatus.ERROR
                return False

        except Exception as e:
            logger.error(f"Failed to load agent {self.file_path}: {e}")
            self.status = AgentStatus.ERROR
            return False

    def _extract_metadata(self) -> AgentMetadata | None:
        """Extract #de_memo metadata from HTML content.

        Returns:
            AgentMetadata if valid agent, None otherwise.
        """
        # Check for kagami:agent meta tag
        if 'name="kagami:agent"' not in self._content:
            return None

        # Extract meta tags - robust to attribute order
        def get_meta(name: str) -> str | None:
            """Extract content from a meta tag, handling any attribute order.

            HTML allows attributes in any order, so we need to handle both:
              <meta name="foo" content="bar">
              <meta content="bar" name="foo">

            Args:
                name: The meta tag name to search for.

            Returns:
                The content value if found, None otherwise.
            """
            # Pattern 1: name before content
            pattern1 = rf'<meta\s+name="{re.escape(name)}"\s+content="([^"]*)"'
            match = re.search(pattern1, self._content)
            if match:
                return match.group(1)

            # Pattern 2: content before name
            pattern2 = rf'<meta\s+content="([^"]*)"\s+name="{re.escape(name)}"'
            match = re.search(pattern2, self._content)
            if match:
                return match.group(1)

            # Pattern 3: attributes with other attributes between (e.g., charset)
            # More permissive: find meta tags with both name and content anywhere
            pattern3 = rf'<meta\s+[^>]*name="{re.escape(name)}"[^>]*content="([^"]*)"[^>]*>'
            match = re.search(pattern3, self._content)
            if match:
                return match.group(1)

            pattern4 = rf'<meta\s+[^>]*content="([^"]*)"[^>]*name="{re.escape(name)}"[^>]*>'
            match = re.search(pattern4, self._content)
            return match.group(1) if match else None

        # Parse capabilities
        capabilities_str = get_meta("kagami:capabilities") or ""
        capabilities = set()
        for cap_str in capabilities_str.split(","):
            cap_str = cap_str.strip()
            if cap_str:
                try:
                    capabilities.add(AgentCapability(cap_str))
                except ValueError:
                    pass

        # Get title from <title> tag
        title_match = re.search(r"<title>([^<]*)</title>", self._content)
        name = title_match.group(1) if title_match else "unnamed-agent"

        # Get description from meta description
        description = get_meta("description") or ""

        # Validate colony name against canonical list
        VALID_COLONIES = {"spark", "forge", "flow", "nexus", "beacon", "grove", "crystal"}
        raw_colony = (get_meta("kagami:colony") or "nexus").lower().strip()
        colony = raw_colony if raw_colony in VALID_COLONIES else "nexus"
        if raw_colony != colony:
            logger.warning(
                f"Invalid colony '{raw_colony}' in {self.file_path}, defaulting to 'nexus'"
            )

        # Validate consensus weight (must be positive integer)
        raw_weight = get_meta("kagami:consensus-weight") or "1"
        try:
            consensus_weight = max(1, int(raw_weight))  # Minimum 1
        except ValueError:
            logger.warning(
                f"Invalid consensus-weight '{raw_weight}' in {self.file_path}, defaulting to 1"
            )
            consensus_weight = 1

        # Parse voice settings with range validation
        def get_float_meta(
            name: str, default: float, min_val: float = 0.0, max_val: float = 1.0
        ) -> float:
            """Extract float from a meta tag with validation and range clamping.

            Args:
                name: Meta tag name to extract.
                default: Default value if not found.
                min_val: Minimum allowed value (inclusive).
                max_val: Maximum allowed value (inclusive).

            Returns:
                Validated and clamped float value.
            """
            raw = get_meta(name)
            if raw is None:
                return default
            try:
                value = float(raw)
                # Clamp to valid range
                if value < min_val or value > max_val:
                    logger.warning(
                        f"Value {value} for {name} out of range [{min_val}, {max_val}], "
                        f"clamping in {self.file_path}"
                    )
                    return max(min_val, min(max_val, value))
                return value
            except ValueError:
                logger.warning(
                    f"Invalid float value '{raw}' for {name} in {self.file_path}, "
                    f"defaulting to {default}"
                )
                return default

        # ElevenLabs voice parameter ranges:
        # - stability: 0.0-1.0 (higher = more consistent, lower = more expressive)
        # - similarity_boost: 0.0-1.0 (higher = more similar to original voice)
        # - style: 0.0-1.0 (higher = more stylized delivery)
        # - speed: 0.5-2.0 (playback speed multiplier)
        voice_stability = get_float_meta("kagami:voice:stability", 0.45, min_val=0.0, max_val=1.0)
        voice_similarity_boost = get_float_meta(
            "kagami:voice:similarity_boost", 0.78, min_val=0.0, max_val=1.0
        )
        voice_style = get_float_meta("kagami:voice:style", 0.32, min_val=0.0, max_val=1.0)
        voice_speed = get_float_meta("kagami:voice:speed", 1.0, min_val=0.5, max_val=2.0)
        personality_prompt = get_meta("kagami:personality") or ""

        return AgentMetadata(
            agent_id=self._content_hash[:16],
            file_path=str(self.file_path),
            name=name,
            version=get_meta("kagami:version") or "1.0.0",
            colony=colony,
            capabilities=capabilities,
            consensus_weight=consensus_weight,
            description=description,
            voice_stability=voice_stability,
            voice_similarity_boost=voice_similarity_boost,
            voice_style=voice_style,
            voice_speed=voice_speed,
            personality_prompt=personality_prompt,
        )

    async def reload_if_changed(self) -> bool:
        """Reload if file has changed.

        Returns:
            True if reloaded, False if unchanged.
        """
        if not self.file_path.exists():
            self.status = AgentStatus.ERROR
            return False

        # Check modification time
        mtime = self.file_path.stat().st_mtime
        if mtime > self._last_loaded:
            return await self.load()

        return False

    def has_capability(self, capability: AgentCapability) -> bool:
        """Check if agent has a capability.

        Args:
            capability: Capability to check.

        Returns:
            True if agent has the capability.
        """
        if not self.metadata:
            return False
        return capability in self.metadata.capabilities

    async def vote(self, proposal_id: str, vote: str) -> dict[str, Any]:
        """Submit a vote on a consensus proposal.

        Args:
            proposal_id: ID of the proposal.
            vote: Vote value ("approve", "reject", "abstain").

        Returns:
            Vote result.
        """
        if not self.metadata:
            return {"success": False, "error": "Agent not loaded"}

        if not self.has_capability(AgentCapability.VOTE):
            return {"success": False, "error": "No voting capability"}

        # Submit vote (would connect to PBFT in production)
        return {
            "success": True,
            "agent_id": self.metadata.agent_id,
            "proposal_id": proposal_id,
            "vote": vote,
            "weight": self.metadata.consensus_weight,
            "timestamp": time.time(),
        }


# =============================================================================
# HTML Agent Registry
# =============================================================================


class HTMLAgentRegistry:
    """Registry for managing HTML agents.

    Scans directories for #de_memo agents, maintains their
    registration, and coordinates consensus participation.

    Example:
        >>> registry = await get_html_agent_registry()
        >>> agents = registry.list_agents()
        >>> capable = registry.find_agents_with_capability(AgentCapability.SMARTHOME)
    """

    def __init__(self, config: AgentConfig | None = None) -> None:
        """Initialize registry.

        Args:
            config: Registry configuration.
        """
        self.config = config or AgentConfig()
        self._agents: dict[str, HTMLAgent] = {}
        self._initialized = False
        self._scan_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the registry."""
        if self._initialized:
            return

        # Ensure directory exists
        agent_dir = Path(self.config.agent_directory)
        agent_dir.mkdir(parents=True, exist_ok=True)

        # Initial scan
        await self.scan_agents()

        # Start background scanning
        self._scan_task = asyncio.create_task(self._scan_loop())

        self._initialized = True
        logger.info(
            f"✅ HTMLAgentRegistry initialized: "
            f"{len(self._agents)} agents in {self.config.agent_directory}"
        )

    async def shutdown(self) -> None:
        """Shutdown the registry."""
        if self._scan_task:
            self._scan_task.cancel()
            try:
                await self._scan_task
            except asyncio.CancelledError:
                pass

        self._initialized = False
        logger.info("🛑 HTMLAgentRegistry shutdown")

    async def scan_agents(self) -> int:
        """Scan directory for HTML agents.

        Returns:
            Number of agents found.
        """
        agent_dir = Path(self.config.agent_directory)
        if not agent_dir.exists():
            return 0

        found = 0
        async with self._lock:
            for html_file in agent_dir.glob("**/*.html"):
                agent = HTMLAgent(html_file)
                if await agent.load():
                    if agent.metadata:
                        self._agents[agent.metadata.agent_id] = agent
                        found += 1

        logger.debug(f"Scanned {found} agents from {agent_dir}")
        return found

    async def _scan_loop(self) -> None:
        """Background scanning loop.

        Periodically scans for new agents and reloads changed ones.
        Uses lock to prevent race conditions when accessing agent registry.
        """
        while True:
            await asyncio.sleep(self.config.scan_interval)
            await self.scan_agents()

            # Reload changed agents (copy list under lock to prevent race)
            async with self._lock:
                agents_snapshot = list(self._agents.values())

            for agent in agents_snapshot:
                await agent.reload_if_changed()

    def register_agent(self, agent: HTMLAgent) -> bool:
        """Manually register an agent.

        Args:
            agent: Agent to register.

        Returns:
            True if registered successfully.
        """
        if not agent.metadata:
            return False

        if len(self._agents) >= self.config.max_agents:
            logger.warning("Max agents reached, cannot register")
            return False

        self._agents[agent.metadata.agent_id] = agent
        return True

    def unregister_agent(self, agent_id: str) -> bool:
        """Unregister an agent.

        Args:
            agent_id: Agent ID to unregister.

        Returns:
            True if unregistered.
        """
        if agent_id in self._agents:
            del self._agents[agent_id]
            return True
        return False

    def get_agent(self, agent_id: str) -> HTMLAgent | None:
        """Get agent by ID.

        Args:
            agent_id: Agent identifier.

        Returns:
            HTMLAgent or None.
        """
        return self._agents.get(agent_id)

    def list_agents(self) -> list[AgentMetadata]:
        """List all registered agents.

        Returns:
            List of agent metadata.
        """
        return [agent.metadata for agent in self._agents.values() if agent.metadata]

    def find_agents_with_capability(
        self,
        capability: AgentCapability,
    ) -> list[HTMLAgent]:
        """Find agents with a specific capability.

        Args:
            capability: Required capability.

        Returns:
            List of matching agents.
        """
        return [agent for agent in self._agents.values() if agent.has_capability(capability)]

    def find_agents_by_colony(self, colony: str) -> list[HTMLAgent]:
        """Find agents aligned with a colony.

        Args:
            colony: Colony name.

        Returns:
            List of matching agents.
        """
        return [
            agent
            for agent in self._agents.values()
            if agent.metadata and agent.metadata.colony == colony
        ]

    def get_all_capabilities(self) -> set[AgentCapability]:
        """Get union of all agent capabilities.

        Returns:
            Set of all capabilities.
        """
        capabilities = set()
        for agent in self._agents.values():
            if agent.metadata:
                capabilities.update(agent.metadata.capabilities)
        return capabilities

    async def call_consensus_vote(
        self,
        proposal_id: str,
        proposal_data: dict[str, Any],
        required_capability: AgentCapability = AgentCapability.VOTE,
    ) -> dict[str, Any]:
        """Call for a consensus vote among capable agents.

        Args:
            proposal_id: Unique proposal identifier.
            proposal_data: Data to vote on.
            required_capability: Capability required to vote.

        Returns:
            Vote results.
        """
        voters = self.find_agents_with_capability(required_capability)

        if not voters:
            return {
                "success": False,
                "error": "No agents with voting capability",
            }

        # Collect votes
        votes: list[dict[str, Any]] = []
        total_weight = 0
        approve_weight = 0

        for agent in voters:
            # Agents currently auto-approve. Production validation would pass
            # proposal_data to agent.validate() before vote() call.
            _ = proposal_data  # Reserved for future proposal validation
            vote_result = await agent.vote(proposal_id, "approve")
            if vote_result.get("success"):
                votes.append(vote_result)
                weight = vote_result.get("weight", 1)
                total_weight += weight
                if vote_result.get("vote") == "approve":
                    approve_weight += weight

        # Calculate result (Byzantine consensus: >50% weighted approval)
        approved = approve_weight > total_weight / 2

        return {
            "success": True,
            "proposal_id": proposal_id,
            "proposal_hash": hashlib.sha256(
                json.dumps(proposal_data, sort_keys=True).encode()
            ).hexdigest()[:16],
            "total_voters": len(voters),
            "votes_received": len(votes),
            "total_weight": total_weight,
            "approve_weight": approve_weight,
            "approved": approved,
            "votes": votes,
        }

    def get_stats(self) -> dict[str, Any]:
        """Get registry statistics.

        Returns:
            Statistics dictionary.
        """
        agents_by_colony: dict[str, int] = {}
        agents_by_status: dict[str, int] = {}
        capabilities_count: dict[str, int] = {}

        for agent in self._agents.values():
            # Count by status
            status = agent.status.name
            agents_by_status[status] = agents_by_status.get(status, 0) + 1

            if agent.metadata:
                # Count by colony
                colony = agent.metadata.colony
                agents_by_colony[colony] = agents_by_colony.get(colony, 0) + 1

                # Count capabilities
                for cap in agent.metadata.capabilities:
                    capabilities_count[cap.value] = capabilities_count.get(cap.value, 0) + 1

        return {
            "total_agents": len(self._agents),
            "by_colony": agents_by_colony,
            "by_status": agents_by_status,
            "capabilities": capabilities_count,
            "scan_interval": self.config.scan_interval,
            "agent_directory": self.config.agent_directory,
        }


# =============================================================================
# Factory Functions
# =============================================================================


_registry: HTMLAgentRegistry | None = None


async def get_html_agent_registry(
    config: AgentConfig | None = None,
) -> HTMLAgentRegistry:
    """Get or create singleton registry.

    Args:
        config: Registry configuration.

    Returns:
        HTMLAgentRegistry instance.
    """
    global _registry

    if _registry is None:
        _registry = HTMLAgentRegistry(config)
        await _registry.initialize()

    return _registry


async def shutdown_html_agent_registry() -> None:
    """Shutdown the registry."""
    global _registry

    if _registry:
        await _registry.shutdown()
        _registry = None


__all__ = [
    "AgentCapability",
    "AgentConfig",
    "AgentMetadata",
    "AgentStatus",
    "HTMLAgent",
    "HTMLAgentRegistry",
    "get_html_agent_registry",
    "shutdown_html_agent_registry",
]
