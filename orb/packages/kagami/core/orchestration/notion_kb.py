"""Notion Knowledge Base — Structured Knowledge Persistence.

This module provides structured knowledge management using Notion:
- Create databases for Research, Decisions, Changelog, Patterns
- Auto-persist Grove research findings
- Log architectural decisions from Beacon
- Store learned patterns from stigmergy

Architecture:
    ┌────────────────────────────────────────────────────────────────────────┐
    │                       NOTION KNOWLEDGE BASE                             │
    │                                                                        │
    │  ┌──────────────────────────────────────────────────────────────────┐  │
    │  │                         DATABASES                                 │  │
    │  │                                                                   │  │
    │  │  Research DB ──► Research findings from Grove                     │  │
    │  │  Decisions DB ──► Architecture decisions from Beacon              │  │
    │  │  Changelog DB ──► Merged PRs and releases                         │  │
    │  │  Patterns DB ──► Learned patterns from stigmergy                  │  │
    │  └──────────────────────────────────────────────────────────────────┘  │
    │                                                                        │
    │  ┌──────────────────────────────────────────────────────────────────┐  │
    │  │                         INTEGRATION                               │  │
    │  │                                                                   │  │
    │  │  Grove Research ──────────────────────────► Research DB           │  │
    │  │  Beacon Decisions ────────────────────────► Decisions DB          │  │
    │  │  GitHub PRs ──────────────────────────────► Changelog DB          │  │
    │  │  Stigmergy Patterns ──────────────────────► Patterns DB           │  │
    │  └──────────────────────────────────────────────────────────────────┘  │
    └────────────────────────────────────────────────────────────────────────┘

Usage:
    from kagami.core.orchestration.notion_kb import get_notion_kb

    kb = await get_notion_kb()

    # Store research finding
    await kb.store_research(
        topic="E8 Lattice Optimization",
        findings="Key finding summary...",
        source="Grove research session",
    )

    # Log architectural decision
    await kb.log_decision(
        title="Use E8 for action routing",
        context="Need efficient routing...",
        decision="Implement E8 lattice...",
        consequences=["+efficiency", "-complexity"],
    )

    # Query knowledge base
    results = await kb.search("E8 lattice")
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kagami.core.services.composio import ComposioIntegrationService

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

# Database configuration
DEFAULT_PARENT_PAGE_ID = ""  # Set via environment or config


class KBEntryType(Enum):
    """Knowledge base entry types."""

    RESEARCH = "research"
    DECISION = "decision"
    CHANGELOG = "changelog"
    PATTERN = "pattern"
    NOTE = "note"


class DecisionStatus(Enum):
    """Status of an architectural decision."""

    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    DEPRECATED = "deprecated"
    SUPERSEDED = "superseded"


class PatternCategory(Enum):
    """Categories for learned patterns."""

    ROUTING = "routing"
    INTEGRATION = "integration"
    ERROR_HANDLING = "error_handling"
    PERFORMANCE = "performance"
    SECURITY = "security"
    OTHER = "other"


@dataclass
class ResearchEntry:
    """A research finding entry."""

    id: str | None = None
    topic: str = ""
    findings: str = ""
    source: str = ""
    colony: str = "grove"  # Which colony produced this
    confidence: float = 0.8
    tags: list[str] = field(default_factory=list)
    references: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def to_notion_properties(self) -> dict[str, Any]:
        """Convert to Notion page properties."""
        return {
            "Topic": {"title": [{"text": {"content": self.topic}}]},
            "Source": {"rich_text": [{"text": {"content": self.source}}]},
            "Colony": {"select": {"name": self.colony}},
            "Confidence": {"number": self.confidence},
            "Tags": {"multi_select": [{"name": tag} for tag in self.tags]},
        }


@dataclass
class DecisionEntry:
    """An architectural decision record (ADR)."""

    id: str | None = None
    title: str = ""
    context: str = ""
    decision: str = ""
    consequences: list[str] = field(default_factory=list)
    status: DecisionStatus = DecisionStatus.PROPOSED
    colony: str = "beacon"
    related_issues: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def to_notion_properties(self) -> dict[str, Any]:
        """Convert to Notion page properties."""
        return {
            "Title": {"title": [{"text": {"content": self.title}}]},
            "Status": {"select": {"name": self.status.value}},
            "Colony": {"select": {"name": self.colony}},
            "Related Issues": {
                "rich_text": [{"text": {"content": ", ".join(self.related_issues)}}]
            },
        }

    def to_markdown(self) -> str:
        """Generate ADR markdown content."""
        consequences_text = "\n".join(f"- {c}" for c in self.consequences)
        return f"""# {self.title}

## Status
{self.status.value.title()}

## Context
{self.context}

## Decision
{self.decision}

## Consequences
{consequences_text}

---
*Created by {self.colony} colony*
"""


@dataclass
class ChangelogEntry:
    """A changelog entry for merged PRs."""

    id: str | None = None
    title: str = ""
    pr_number: int | None = None
    pr_url: str = ""
    description: str = ""
    author: str = ""
    merged_at: str = ""
    labels: list[str] = field(default_factory=list)

    def to_notion_properties(self) -> dict[str, Any]:
        """Convert to Notion page properties."""
        return {
            "Title": {"title": [{"text": {"content": self.title}}]},
            "PR Number": {"number": self.pr_number},
            "Author": {"rich_text": [{"text": {"content": self.author}}]},
            "Labels": {"multi_select": [{"name": label} for label in self.labels]},
        }


@dataclass
class PatternEntry:
    """A learned pattern from stigmergy."""

    id: str | None = None
    name: str = ""
    category: PatternCategory = PatternCategory.OTHER
    description: str = ""
    success_rate: float = 0.0
    usage_count: int = 0
    colonies_involved: list[str] = field(default_factory=list)
    services_involved: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)

    def to_notion_properties(self) -> dict[str, Any]:
        """Convert to Notion page properties."""
        return {
            "Name": {"title": [{"text": {"content": self.name}}]},
            "Category": {"select": {"name": self.category.value}},
            "Success Rate": {"number": self.success_rate},
            "Usage Count": {"number": self.usage_count},
            "Colonies": {"multi_select": [{"name": c} for c in self.colonies_involved]},
            "Services": {"multi_select": [{"name": s} for s in self.services_involved]},
        }


# =============================================================================
# NOTION KNOWLEDGE BASE
# =============================================================================


class NotionKnowledgeBase:
    """Structured knowledge base using Notion.

    This class provides high-level operations for managing knowledge:

    1. Research Storage: Persist findings from Grove research
    2. Decision Logging: Track architectural decisions from Beacon
    3. Changelog Management: Log merged PRs and releases
    4. Pattern Storage: Store learned patterns from stigmergy
    5. Knowledge Retrieval: Search and query the knowledge base
    """

    def __init__(
        self,
        parent_page_id: str = DEFAULT_PARENT_PAGE_ID,
    ) -> None:
        """Initialize Notion knowledge base.

        Args:
            parent_page_id: Parent page for KB databases
        """
        self.parent_page_id = parent_page_id

        self._composio: ComposioIntegrationService | None = None
        self._initialized = False

        # Database IDs (discovered or created)
        self._db_ids: dict[KBEntryType, str] = {}

        # Cache
        self._research_cache: dict[str, ResearchEntry] = {}
        self._decision_cache: dict[str, DecisionEntry] = {}
        self._changelog_cache: dict[str, ChangelogEntry] = {}
        self._pattern_cache: dict[str, PatternEntry] = {}

    async def initialize(self) -> bool:
        """Initialize the Notion knowledge base.

        Returns:
            True if successfully initialized
        """
        if self._initialized:
            return True

        try:
            from kagami.core.services.composio import get_composio_service

            self._composio = get_composio_service()
            await self._composio.initialize()

            if not self._composio.initialized:
                logger.warning("Composio not initialized - Notion KB disabled")
                return False

            # Verify Notion is connected
            apps = await self._composio.get_connected_apps()
            notion_connected = any(app.get("toolkit") == "notion" for app in apps)

            if not notion_connected:
                logger.warning("Notion not connected to Composio - run 'composio add notion'")
                return False

            # Discover or create databases
            await self._setup_databases()

            self._initialized = True
            logger.info("✅ NotionKnowledgeBase initialized")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize NotionKnowledgeBase: {e}")
            return False

    async def _setup_databases(self) -> None:
        """Setup or discover KB databases."""
        if not self._composio:
            return

        # For now, we'll create pages directly
        # In a full implementation, we'd create databases with schemas
        logger.debug("Notion KB databases ready (using pages)")

    # =========================================================================
    # RESEARCH STORAGE
    # =========================================================================

    async def store_research(
        self,
        topic: str,
        findings: str,
        source: str = "grove",
        colony: str = "grove",
        confidence: float = 0.8,
        tags: list[str] | None = None,
        references: list[str] | None = None,
    ) -> ResearchEntry | None:
        """Store a research finding.

        Args:
            topic: Research topic
            findings: Key findings
            source: Source of research
            colony: Colony that produced it
            confidence: Confidence level (0-1)
            tags: Tags for categorization
            references: Reference links

        Returns:
            ResearchEntry if successful, None otherwise
        """
        await self.initialize()

        if not self._composio:
            return None

        entry = ResearchEntry(
            topic=topic,
            findings=findings,
            source=source,
            colony=colony,
            confidence=confidence,
            tags=tags or [],
            references=references or [],
        )

        try:
            # Create Notion page
            content = f"""# {topic}

## Findings
{findings}

## Source
{source}

## Confidence
{confidence * 100:.0f}%

## Tags
{", ".join(tags or ["untagged"])}

## References
{"".join(f"- {ref}" + chr(10) for ref in (references or [])) or "None"}

---
*Stored by {colony} colony at {datetime.now(UTC).isoformat()}*
"""

            result = await self._composio.execute_action(
                "NOTION_CREATE_NOTION_PAGE",
                {
                    "title": f"Research: {topic}",
                    "content": content,
                },
            )

            page_id = result.get("data", {}).get("id")
            if page_id:
                entry.id = page_id
                self._research_cache[page_id] = entry
                logger.info(f"✅ Stored research: {topic}")
                return entry

            logger.warning(f"Failed to store research: {result}")
            return None

        except Exception as e:
            logger.error(f"Failed to store research: {e}")
            return None

    async def get_research(self, topic: str | None = None, limit: int = 10) -> list[ResearchEntry]:
        """Get research entries.

        Args:
            topic: Filter by topic (partial match)
            limit: Maximum entries to return

        Returns:
            List of ResearchEntry objects
        """
        await self.initialize()

        if not self._composio:
            return []

        try:
            result = await self._composio.execute_action(
                "NOTION_SEARCH_NOTION_PAGE",
                {
                    "query": f"Research: {topic}" if topic else "Research:",
                },
            )

            pages = result.get("data", {}).get("results", [])[:limit]

            entries = []
            for page in pages:
                # Parse page back to ResearchEntry (simplified)
                title = (
                    page.get("properties", {})
                    .get("title", {})
                    .get("title", [{}])[0]
                    .get("text", {})
                    .get("content", "")
                )
                if title.startswith("Research: "):
                    entries.append(
                        ResearchEntry(
                            id=page.get("id"),
                            topic=title.replace("Research: ", ""),
                        )
                    )

            return entries

        except Exception as e:
            logger.error(f"Failed to get research: {e}")
            return []

    # =========================================================================
    # DECISION LOGGING
    # =========================================================================

    async def log_decision(
        self,
        title: str,
        context: str,
        decision: str,
        consequences: list[str] | None = None,
        status: DecisionStatus = DecisionStatus.ACCEPTED,
        colony: str = "beacon",
        related_issues: list[str] | None = None,
    ) -> DecisionEntry | None:
        """Log an architectural decision.

        Args:
            title: Decision title
            context: Context and background
            decision: The decision made
            consequences: Expected consequences
            status: Decision status
            colony: Colony that made it
            related_issues: Related issue IDs

        Returns:
            DecisionEntry if successful, None otherwise
        """
        await self.initialize()

        if not self._composio:
            return None

        entry = DecisionEntry(
            title=title,
            context=context,
            decision=decision,
            consequences=consequences or [],
            status=status,
            colony=colony,
            related_issues=related_issues or [],
        )

        try:
            result = await self._composio.execute_action(
                "NOTION_CREATE_NOTION_PAGE",
                {
                    "title": f"ADR: {title}",
                    "content": entry.to_markdown(),
                },
            )

            page_id = result.get("data", {}).get("id")
            if page_id:
                entry.id = page_id
                self._decision_cache[page_id] = entry
                logger.info(f"✅ Logged decision: {title}")
                return entry

            logger.warning(f"Failed to log decision: {result}")
            return None

        except Exception as e:
            logger.error(f"Failed to log decision: {e}")
            return None

    async def get_decisions(
        self,
        status: DecisionStatus | None = None,
        limit: int = 10,
    ) -> list[DecisionEntry]:
        """Get decision entries.

        Args:
            status: Filter by status
            limit: Maximum entries to return

        Returns:
            List of DecisionEntry objects
        """
        await self.initialize()

        if not self._composio:
            return []

        try:
            result = await self._composio.execute_action(
                "NOTION_SEARCH_NOTION_PAGE",
                {
                    "query": "ADR:",
                },
            )

            pages = result.get("data", {}).get("results", [])[:limit]

            entries = []
            for page in pages:
                title = (
                    page.get("properties", {})
                    .get("title", {})
                    .get("title", [{}])[0]
                    .get("text", {})
                    .get("content", "")
                )
                if title.startswith("ADR: "):
                    entries.append(
                        DecisionEntry(
                            id=page.get("id"),
                            title=title.replace("ADR: ", ""),
                        )
                    )

            return entries

        except Exception as e:
            logger.error(f"Failed to get decisions: {e}")
            return []

    # =========================================================================
    # CHANGELOG MANAGEMENT
    # =========================================================================

    async def log_changelog(
        self,
        title: str,
        pr_number: int | None = None,
        pr_url: str = "",
        description: str = "",
        author: str = "",
        labels: list[str] | None = None,
    ) -> ChangelogEntry | None:
        """Log a changelog entry.

        Args:
            title: Entry title (usually PR title)
            pr_number: GitHub PR number
            pr_url: GitHub PR URL
            description: Description of changes
            author: Author username
            labels: PR labels

        Returns:
            ChangelogEntry if successful, None otherwise
        """
        await self.initialize()

        if not self._composio:
            return None

        entry = ChangelogEntry(
            title=title,
            pr_number=pr_number,
            pr_url=pr_url,
            description=description,
            author=author,
            merged_at=datetime.now(UTC).isoformat(),
            labels=labels or [],
        )

        try:
            content = f"""# {title}

## PR Details
- **Number:** #{pr_number or "N/A"}
- **URL:** {pr_url or "N/A"}
- **Author:** {author or "Unknown"}
- **Labels:** {", ".join(labels or ["none"])}

## Description
{description or "No description provided."}

---
*Merged at {entry.merged_at}*
"""

            result = await self._composio.execute_action(
                "NOTION_CREATE_NOTION_PAGE",
                {
                    "title": f"Changelog: {title}",
                    "content": content,
                },
            )

            page_id = result.get("data", {}).get("id")
            if page_id:
                entry.id = page_id
                self._changelog_cache[page_id] = entry
                logger.info(f"✅ Logged changelog: {title}")
                return entry

            return None

        except Exception as e:
            logger.error(f"Failed to log changelog: {e}")
            return None

    # =========================================================================
    # PATTERN STORAGE
    # =========================================================================

    async def store_pattern(
        self,
        name: str,
        category: PatternCategory,
        description: str,
        success_rate: float = 0.0,
        usage_count: int = 0,
        colonies_involved: list[str] | None = None,
        services_involved: list[str] | None = None,
    ) -> PatternEntry | None:
        """Store a learned pattern.

        Args:
            name: Pattern name
            category: Pattern category
            description: Pattern description
            success_rate: Historical success rate
            usage_count: Number of times used
            colonies_involved: Colonies that use this pattern
            services_involved: Services involved in pattern

        Returns:
            PatternEntry if successful, None otherwise
        """
        await self.initialize()

        if not self._composio:
            return None

        entry = PatternEntry(
            name=name,
            category=category,
            description=description,
            success_rate=success_rate,
            usage_count=usage_count,
            colonies_involved=colonies_involved or [],
            services_involved=services_involved or [],
        )

        try:
            content = f"""# Pattern: {name}

## Category
{category.value.replace("_", " ").title()}

## Description
{description}

## Metrics
- **Success Rate:** {success_rate * 100:.1f}%
- **Usage Count:** {usage_count}

## Colonies
{", ".join(colonies_involved or ["none"])}

## Services
{", ".join(services_involved or ["none"])}

---
*Last updated: {datetime.now(UTC).isoformat()}*
"""

            result = await self._composio.execute_action(
                "NOTION_CREATE_NOTION_PAGE",
                {
                    "title": f"Pattern: {name}",
                    "content": content,
                },
            )

            page_id = result.get("data", {}).get("id")
            if page_id:
                entry.id = page_id
                self._pattern_cache[page_id] = entry
                logger.info(f"✅ Stored pattern: {name}")
                return entry

            return None

        except Exception as e:
            logger.error(f"Failed to store pattern: {e}")
            return None

    async def get_patterns(
        self,
        category: PatternCategory | None = None,
        min_success_rate: float = 0.0,
        limit: int = 10,
    ) -> list[PatternEntry]:
        """Get pattern entries.

        Args:
            category: Filter by category
            min_success_rate: Minimum success rate filter
            limit: Maximum entries to return

        Returns:
            List of PatternEntry objects
        """
        await self.initialize()

        if not self._composio:
            return []

        try:
            result = await self._composio.execute_action(
                "NOTION_SEARCH_NOTION_PAGE",
                {
                    "query": "Pattern:",
                },
            )

            pages = result.get("data", {}).get("results", [])[:limit]

            entries = []
            for page in pages:
                title = (
                    page.get("properties", {})
                    .get("title", {})
                    .get("title", [{}])[0]
                    .get("text", {})
                    .get("content", "")
                )
                if title.startswith("Pattern: "):
                    entries.append(
                        PatternEntry(
                            id=page.get("id"),
                            name=title.replace("Pattern: ", ""),
                        )
                    )

            return entries

        except Exception as e:
            logger.error(f"Failed to get patterns: {e}")
            return []

    # =========================================================================
    # SEARCH
    # =========================================================================

    async def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Search across all knowledge base entries.

        Args:
            query: Search query
            limit: Maximum results to return

        Returns:
            List of search results with type and entry
        """
        await self.initialize()

        if not self._composio:
            return []

        try:
            result = await self._composio.execute_action(
                "NOTION_SEARCH_NOTION_PAGE",
                {
                    "query": query,
                },
            )

            pages = result.get("data", {}).get("results", [])[:limit]

            results = []
            for page in pages:
                title = (
                    page.get("properties", {})
                    .get("title", {})
                    .get("title", [{}])[0]
                    .get("text", {})
                    .get("content", "")
                )

                # Determine type from title prefix
                entry_type = KBEntryType.NOTE
                if title.startswith("Research:"):
                    entry_type = KBEntryType.RESEARCH
                elif title.startswith("ADR:"):
                    entry_type = KBEntryType.DECISION
                elif title.startswith("Changelog:"):
                    entry_type = KBEntryType.CHANGELOG
                elif title.startswith("Pattern:"):
                    entry_type = KBEntryType.PATTERN

                results.append(
                    {
                        "type": entry_type.value,
                        "id": page.get("id"),
                        "title": title,
                        "url": page.get("url", ""),
                    }
                )

            return results

        except Exception as e:
            logger.error(f"Failed to search KB: {e}")
            return []

    # =========================================================================
    # STATUS
    # =========================================================================

    def get_status(self) -> dict[str, Any]:
        """Get KB status summary."""
        return {
            "initialized": self._initialized,
            "cached_research": len(self._research_cache),
            "cached_decisions": len(self._decision_cache),
            "cached_changelog": len(self._changelog_cache),
            "cached_patterns": len(self._pattern_cache),
        }


# =============================================================================
# SINGLETON
# =============================================================================

_notion_kb: NotionKnowledgeBase | None = None


def get_notion_kb() -> NotionKnowledgeBase:
    """Get the global Notion knowledge base instance."""
    global _notion_kb
    if _notion_kb is None:
        _notion_kb = NotionKnowledgeBase()
    return _notion_kb


async def initialize_notion_kb() -> NotionKnowledgeBase:
    """Initialize and return the global Notion knowledge base."""
    kb = get_notion_kb()
    await kb.initialize()
    return kb


__all__ = [
    "ChangelogEntry",
    "DecisionEntry",
    "DecisionStatus",
    "KBEntryType",
    "NotionKnowledgeBase",
    "PatternCategory",
    "PatternEntry",
    "ResearchEntry",
    "get_notion_kb",
    "initialize_notion_kb",
]
