"""Linear Sprint Sync — Automated Sprint and Cycle Management.

This module provides automated synchronization between Linear and GitHub:
- Sync Linear cycles with GitHub milestones
- Auto-create Linear issues from GitHub PRs
- Track velocity across sprints
- Generate sprint reports to Notion

Architecture:
    ┌────────────────────────────────────────────────────────────────────────┐
    │                       LINEAR SPRINT SYNC                                │
    │                                                                        │
    │  ┌──────────────────────────────────────────────────────────────────┐  │
    │  │                        CYCLE TRACKING                             │  │
    │  │                                                                   │  │
    │  │  Linear Cycle ←──→ GitHub Milestone ←──→ Notion Sprint Doc        │  │
    │  │       │                    │                     │                │  │
    │  │       ▼                    ▼                     ▼                │  │
    │  │  Issues ←──────────→ PRs ←──────────→ Changelog                   │  │
    │  └──────────────────────────────────────────────────────────────────┘  │
    │                                                                        │
    │  ┌──────────────────────────────────────────────────────────────────┐  │
    │  │                        VELOCITY TRACKING                          │  │
    │  │                                                                   │  │
    │  │  Points Started → Points Completed → Points Velocity              │  │
    │  │       │                  │                  │                     │  │
    │  │       └──────────────────┴──────────────────┘                     │  │
    │  │                         │                                         │  │
    │  │                    Sprint Report                                  │  │
    │  └──────────────────────────────────────────────────────────────────┘  │
    └────────────────────────────────────────────────────────────────────────┘

Usage:
    from kagami.core.orchestration.linear_sync import get_linear_sync

    sync = await get_linear_sync()

    # Get current cycle
    cycle = await sync.get_current_cycle()

    # Sync cycle to GitHub milestone
    await sync.sync_cycle_to_milestone(cycle.id)

    # Generate sprint report
    report = await sync.generate_sprint_report(cycle.id)
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

# Default team settings
DEFAULT_TEAM_KEY = "KAG"


class IssueState(Enum):
    """Linear issue state categories."""

    BACKLOG = "backlog"
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    IN_REVIEW = "in_review"
    DONE = "done"
    CANCELLED = "cancelled"


class IssuePriority(Enum):
    """Linear issue priority levels."""

    NO_PRIORITY = 0
    URGENT = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4


@dataclass
class CycleInfo:
    """Information about a Linear cycle (sprint)."""

    id: str
    number: int
    name: str | None
    starts_at: str
    ends_at: str
    progress: float = 0.0  # 0.0 to 1.0
    scope_completed: int = 0
    scope_total: int = 0
    team_id: str = ""

    @property
    def display_name(self) -> str:
        """Get display name for the cycle."""
        return self.name or f"Sprint {self.number}"

    @property
    def is_active(self) -> bool:
        """Check if cycle is currently active."""
        now = datetime.now(UTC)
        start = datetime.fromisoformat(self.starts_at.replace("Z", "+00:00"))
        end = datetime.fromisoformat(self.ends_at.replace("Z", "+00:00"))
        return start <= now <= end


@dataclass
class IssueInfo:
    """Information about a Linear issue."""

    id: str
    identifier: str  # e.g., "KAG-123"
    title: str
    description: str | None = None
    state: IssueState = IssueState.TODO
    priority: IssuePriority = IssuePriority.NO_PRIORITY
    estimate: int | None = None  # Story points
    cycle_id: str | None = None
    assignee_id: str | None = None
    labels: list[str] = field(default_factory=list)
    github_pr_url: str | None = None

    @property
    def is_completed(self) -> bool:
        """Check if issue is in a completed state."""
        return self.state in (IssueState.DONE, IssueState.CANCELLED)


@dataclass
class VelocityMetrics:
    """Velocity metrics for a sprint."""

    cycle_id: str
    cycle_number: int
    points_planned: int = 0
    points_completed: int = 0
    issues_planned: int = 0
    issues_completed: int = 0
    carry_over: int = 0  # Points not completed

    @property
    def velocity(self) -> float:
        """Calculate velocity as percentage completed."""
        if self.points_planned == 0:
            return 0.0
        return self.points_completed / self.points_planned

    @property
    def completion_rate(self) -> float:
        """Calculate issue completion rate."""
        if self.issues_planned == 0:
            return 0.0
        return self.issues_completed / self.issues_planned


@dataclass
class SprintReport:
    """Sprint report with metrics and summary."""

    cycle: CycleInfo
    velocity: VelocityMetrics
    completed_issues: list[IssueInfo]
    in_progress_issues: list[IssueInfo]
    not_started_issues: list[IssueInfo]
    highlights: list[str] = field(default_factory=list)
    generated_at: float = field(default_factory=time.time)

    def to_markdown(self) -> str:
        """Generate markdown report."""
        lines = [
            f"# Sprint Report: {self.cycle.display_name}",
            "",
            f"**Period:** {self.cycle.starts_at[:10]} to {self.cycle.ends_at[:10]}",
            f"**Progress:** {self.cycle.progress * 100:.0f}%",
            "",
            "## Velocity",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Points Planned | {self.velocity.points_planned} |",
            f"| Points Completed | {self.velocity.points_completed} |",
            f"| Velocity | {self.velocity.velocity * 100:.0f}% |",
            f"| Issues Planned | {self.velocity.issues_planned} |",
            f"| Issues Completed | {self.velocity.issues_completed} |",
            f"| Carry Over | {self.velocity.carry_over} |",
            "",
        ]

        if self.completed_issues:
            lines.extend(
                [
                    "## Completed",
                    "",
                ]
            )
            for issue in self.completed_issues:
                points = f" ({issue.estimate}pts)" if issue.estimate else ""
                lines.append(f"- ✅ {issue.identifier}: {issue.title}{points}")
            lines.append("")

        if self.in_progress_issues:
            lines.extend(
                [
                    "## In Progress",
                    "",
                ]
            )
            for issue in self.in_progress_issues:
                points = f" ({issue.estimate}pts)" if issue.estimate else ""
                lines.append(f"- 🔄 {issue.identifier}: {issue.title}{points}")
            lines.append("")

        if self.not_started_issues:
            lines.extend(
                [
                    "## Not Started (Carry Over)",
                    "",
                ]
            )
            for issue in self.not_started_issues:
                points = f" ({issue.estimate}pts)" if issue.estimate else ""
                lines.append(f"- ⏳ {issue.identifier}: {issue.title}{points}")
            lines.append("")

        if self.highlights:
            lines.extend(
                [
                    "## Highlights",
                    "",
                ]
            )
            for highlight in self.highlights:
                lines.append(f"- {highlight}")
            lines.append("")

        return "\n".join(lines)


# =============================================================================
# LINEAR SPRINT SYNC
# =============================================================================


class LinearSprintSync:
    """Automated Linear sprint synchronization.

    This class provides high-level operations for managing sprints:

    1. Cycle Tracking: Monitor and manage Linear cycles
    2. Issue Management: Create and update issues
    3. GitHub Integration: Sync with milestones and PRs
    4. Velocity Tracking: Calculate and track sprint velocity
    5. Reporting: Generate sprint reports
    """

    def __init__(
        self,
        team_key: str = DEFAULT_TEAM_KEY,
    ) -> None:
        """Initialize Linear sprint sync.

        Args:
            team_key: Linear team key (e.g., "KAG")
        """
        self.team_key = team_key
        self._team_id: str | None = None

        self._composio: ComposioIntegrationService | None = None
        self._initialized = False

        # Cache
        self._cycles: dict[str, CycleInfo] = {}
        self._issues: dict[str, IssueInfo] = {}
        self._velocity_history: list[VelocityMetrics] = []

    async def initialize(self) -> bool:
        """Initialize the Linear sync.

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
                logger.warning("Composio not initialized - Linear sync disabled")
                return False

            # Verify Linear is connected
            apps = await self._composio.get_connected_apps()
            linear_connected = any(app.get("toolkit") == "linear" for app in apps)

            if not linear_connected:
                logger.warning("Linear not connected to Composio - run 'composio add linear'")
                return False

            # Get team ID
            await self._fetch_team_id()

            self._initialized = True
            logger.info(f"✅ LinearSprintSync initialized: team={self.team_key}")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize LinearSprintSync: {e}")
            return False

    async def _fetch_team_id(self) -> None:
        """Fetch and cache the team ID."""
        if not self._composio:
            return

        try:
            result = await self._composio.execute_action("LINEAR_GET_ALL_LINEAR_TEAMS", {})

            teams = result.get("data", {}).get("teams", {}).get("nodes", [])

            for team in teams:
                if team.get("key") == self.team_key:
                    self._team_id = team.get("id")
                    logger.debug(f"Found team ID: {self._team_id}")
                    return

            logger.warning(f"Team {self.team_key} not found in Linear")

        except Exception as e:
            logger.error(f"Failed to fetch team ID: {e}")

    # =========================================================================
    # CYCLE MANAGEMENT
    # =========================================================================

    async def get_cycles(
        self,
        include_past: bool = False,
        include_future: bool = True,
        limit: int = 10,
    ) -> list[CycleInfo]:
        """Get cycles for the team.

        Args:
            include_past: Include completed cycles
            include_future: Include future cycles
            limit: Maximum number of cycles to return

        Returns:
            List of CycleInfo objects
        """
        await self.initialize()

        if not self._composio or not self._team_id:
            return []

        try:
            result = await self._composio.execute_action(
                "LINEAR_GET_CYCLES_BY_TEAM_ID", {"teamId": self._team_id}
            )

            cycles_data = result.get("data", {}).get("team", {}).get("cycles", {}).get("nodes", [])

            cycles = []
            for cycle in cycles_data[:limit]:
                cycle_info = CycleInfo(
                    id=cycle.get("id", ""),
                    number=cycle.get("number", 0),
                    name=cycle.get("name"),
                    starts_at=cycle.get("startsAt", ""),
                    ends_at=cycle.get("endsAt", ""),
                    progress=cycle.get("progress", 0.0),
                    scope_completed=cycle.get("completedScopeCount", 0),
                    scope_total=cycle.get("scopeCount", 0),
                    team_id=self._team_id,
                )

                self._cycles[cycle_info.id] = cycle_info

                # Filter based on include flags
                now = datetime.now(UTC)
                try:
                    end = datetime.fromisoformat(cycle_info.ends_at.replace("Z", "+00:00"))
                    start = datetime.fromisoformat(cycle_info.starts_at.replace("Z", "+00:00"))

                    is_past = end < now
                    is_future = start > now

                    if is_past and not include_past:
                        continue
                    if is_future and not include_future:
                        continue
                except (ValueError, AttributeError):
                    pass

                cycles.append(cycle_info)

            return cycles

        except Exception as e:
            logger.error(f"Failed to get cycles: {e}")
            return []

    async def get_current_cycle(self) -> CycleInfo | None:
        """Get the currently active cycle.

        Returns:
            CycleInfo for current cycle, or None
        """
        cycles = await self.get_cycles(include_past=False, include_future=False)

        for cycle in cycles:
            if cycle.is_active:
                return cycle

        # If no active cycle, return the most recent one
        if cycles:
            return cycles[0]

        return None

    async def get_cycle_issues(self, cycle_id: str) -> list[IssueInfo]:
        """Get all issues in a cycle.

        Args:
            cycle_id: Cycle ID

        Returns:
            List of IssueInfo objects
        """
        await self.initialize()

        if not self._composio:
            return []

        try:
            # Use GraphQL query through available action
            result = await self._composio.execute_action(
                "LINEAR_LIST_LINEAR_ISSUES",
                {
                    "cycleId": cycle_id,
                },
            )

            issues_data = result.get("data", {}).get("issues", {}).get("nodes", [])

            issues = []
            for issue in issues_data:
                # Map state to enum
                state_name = issue.get("state", {}).get("type", "todo").lower()
                state_map = {
                    "backlog": IssueState.BACKLOG,
                    "unstarted": IssueState.TODO,
                    "started": IssueState.IN_PROGRESS,
                    "completed": IssueState.DONE,
                    "canceled": IssueState.CANCELLED,
                    "cancelled": IssueState.CANCELLED,
                }
                state = state_map.get(state_name, IssueState.TODO)

                issue_info = IssueInfo(
                    id=issue.get("id", ""),
                    identifier=issue.get("identifier", ""),
                    title=issue.get("title", ""),
                    description=issue.get("description"),
                    state=state,
                    priority=IssuePriority(issue.get("priority", 0)),
                    estimate=issue.get("estimate"),
                    cycle_id=cycle_id,
                    assignee_id=issue.get("assignee", {}).get("id")
                    if issue.get("assignee")
                    else None,
                    labels=[l.get("name", "") for l in issue.get("labels", {}).get("nodes", [])],
                )

                self._issues[issue_info.id] = issue_info
                issues.append(issue_info)

            return issues

        except Exception as e:
            logger.error(f"Failed to get cycle issues: {e}")
            return []

    # =========================================================================
    # ISSUE MANAGEMENT
    # =========================================================================

    async def create_issue(
        self,
        title: str,
        description: str | None = None,
        priority: IssuePriority = IssuePriority.NO_PRIORITY,
        estimate: int | None = None,
        cycle_id: str | None = None,
        labels: list[str] | None = None,
    ) -> IssueInfo | None:
        """Create a new Linear issue.

        Args:
            title: Issue title
            description: Issue description
            priority: Priority level
            estimate: Story point estimate
            cycle_id: Cycle to add to
            labels: Label names to apply

        Returns:
            IssueInfo if successful, None otherwise
        """
        await self.initialize()

        if not self._composio or not self._team_id:
            return None

        try:
            params: dict[str, Any] = {
                "teamId": self._team_id,
                "title": title,
            }

            if description:
                params["description"] = description
            if priority != IssuePriority.NO_PRIORITY:
                params["priority"] = priority.value
            if estimate:
                params["estimate"] = estimate
            if cycle_id:
                params["cycleId"] = cycle_id

            result = await self._composio.execute_action(
                "LINEAR_CREATE_LINEAR_ISSUE",
                params,
            )

            issue_data = result.get("data", {}).get("issueCreate", {}).get("issue", {})

            if not issue_data.get("id"):
                logger.error(f"Failed to create issue: {result}")
                return None

            issue_info = IssueInfo(
                id=issue_data["id"],
                identifier=issue_data.get("identifier", ""),
                title=title,
                description=description,
                priority=priority,
                estimate=estimate,
                cycle_id=cycle_id,
                labels=labels or [],
            )

            self._issues[issue_info.id] = issue_info
            logger.info(f"✅ Created issue: {issue_info.identifier}")

            return issue_info

        except Exception as e:
            logger.error(f"Failed to create issue: {e}")
            return None

    async def create_issue_from_pr(
        self,
        pr_title: str,
        pr_url: str,
        pr_body: str | None = None,
        cycle_id: str | None = None,
    ) -> IssueInfo | None:
        """Create a Linear issue from a GitHub PR.

        Args:
            pr_title: PR title
            pr_url: PR URL
            pr_body: PR description
            cycle_id: Cycle to add to (uses current if None)

        Returns:
            IssueInfo if successful, None otherwise
        """
        # Use current cycle if not specified
        if cycle_id is None:
            current_cycle = await self.get_current_cycle()
            if current_cycle:
                cycle_id = current_cycle.id

        description = f"GitHub PR: {pr_url}"
        if pr_body:
            description = f"{description}\n\n---\n\n{pr_body}"

        issue = await self.create_issue(
            title=pr_title,
            description=description,
            priority=IssuePriority.MEDIUM,
            cycle_id=cycle_id,
        )

        if issue:
            issue.github_pr_url = pr_url

        return issue

    async def update_issue(
        self,
        issue_id: str,
        state: IssueState | None = None,
        priority: IssuePriority | None = None,
        estimate: int | None = None,
        cycle_id: str | None = None,
    ) -> bool:
        """Update an existing issue.

        Args:
            issue_id: Issue ID
            state: New state
            priority: New priority
            estimate: New estimate
            cycle_id: New cycle

        Returns:
            True if updated successfully
        """
        await self.initialize()

        if not self._composio:
            return False

        try:
            params: dict[str, Any] = {
                "issueId": issue_id,
            }

            if priority is not None:
                params["priority"] = priority.value
            if estimate is not None:
                params["estimate"] = estimate
            if cycle_id is not None:
                params["cycleId"] = cycle_id

            _result = await self._composio.execute_action(
                "LINEAR_UPDATE_ISSUE",
                params,
            )

            if issue_id in self._issues:
                if state is not None:
                    self._issues[issue_id].state = state
                if priority is not None:
                    self._issues[issue_id].priority = priority
                if estimate is not None:
                    self._issues[issue_id].estimate = estimate
                if cycle_id is not None:
                    self._issues[issue_id].cycle_id = cycle_id

            logger.debug(f"Updated issue {issue_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to update issue {issue_id}: {e}")
            return False

    # =========================================================================
    # VELOCITY TRACKING
    # =========================================================================

    async def calculate_velocity(self, cycle_id: str) -> VelocityMetrics:
        """Calculate velocity metrics for a cycle.

        Args:
            cycle_id: Cycle ID

        Returns:
            VelocityMetrics for the cycle
        """
        cycle = self._cycles.get(cycle_id) or await self.get_current_cycle()
        if not cycle:
            return VelocityMetrics(cycle_id=cycle_id, cycle_number=0)

        issues = await self.get_cycle_issues(cycle_id)

        points_planned = 0
        points_completed = 0
        issues_completed = 0

        for issue in issues:
            estimate = issue.estimate or 0
            points_planned += estimate

            if issue.is_completed:
                points_completed += estimate
                issues_completed += 1

        metrics = VelocityMetrics(
            cycle_id=cycle_id,
            cycle_number=cycle.number,
            points_planned=points_planned,
            points_completed=points_completed,
            issues_planned=len(issues),
            issues_completed=issues_completed,
            carry_over=points_planned - points_completed,
        )

        self._velocity_history.append(metrics)

        return metrics

    def get_average_velocity(self, num_sprints: int = 3) -> float:
        """Get average velocity over recent sprints.

        Args:
            num_sprints: Number of sprints to average

        Returns:
            Average velocity (points per sprint)
        """
        if not self._velocity_history:
            return 0.0

        recent = self._velocity_history[-num_sprints:]
        total_points = sum(v.points_completed for v in recent)

        return total_points / len(recent)

    # =========================================================================
    # REPORTING
    # =========================================================================

    async def generate_sprint_report(self, cycle_id: str | None = None) -> SprintReport:
        """Generate a sprint report.

        Args:
            cycle_id: Cycle ID (uses current if None)

        Returns:
            SprintReport with metrics and details
        """
        # Get cycle
        if cycle_id:
            cycle = self._cycles.get(cycle_id)
            if not cycle:
                cycles = await self.get_cycles()
                cycle = next((c for c in cycles if c.id == cycle_id), None)
        else:
            cycle = await self.get_current_cycle()

        if not cycle:
            raise ValueError("No cycle found")

        # Get issues
        issues = await self.get_cycle_issues(cycle.id)

        # Calculate velocity
        velocity = await self.calculate_velocity(cycle.id)

        # Categorize issues
        completed = [i for i in issues if i.state == IssueState.DONE]
        in_progress = [i for i in issues if i.state == IssueState.IN_PROGRESS]
        not_started = [i for i in issues if i.state in (IssueState.TODO, IssueState.BACKLOG)]

        # Generate highlights
        highlights = []
        if velocity.velocity >= 1.0:
            highlights.append("🎉 All planned work completed!")
        elif velocity.velocity >= 0.8:
            highlights.append("✅ Strong sprint - 80%+ completion")
        elif velocity.velocity < 0.5:
            highlights.append("⚠️ Below 50% completion - review scope")

        if velocity.carry_over > 0:
            highlights.append(f"📋 {velocity.carry_over} points carried to next sprint")

        return SprintReport(
            cycle=cycle,
            velocity=velocity,
            completed_issues=completed,
            in_progress_issues=in_progress,
            not_started_issues=not_started,
            highlights=highlights,
        )

    # =========================================================================
    # GITHUB SYNC
    # =========================================================================

    async def sync_cycle_to_milestone(self, cycle_id: str) -> bool:
        """Sync a Linear cycle to a GitHub milestone.

        Args:
            cycle_id: Cycle ID

        Returns:
            True if synced successfully
        """
        await self.initialize()

        if not self._composio:
            return False

        cycle = self._cycles.get(cycle_id)
        if not cycle:
            cycles = await self.get_cycles()
            cycle = next((c for c in cycles if c.id == cycle_id), None)

        if not cycle:
            logger.error(f"Cycle {cycle_id} not found")
            return False

        try:
            # Create or update GitHub milestone
            _result = await self._composio.execute_action(
                "GITHUB_CREATE_A_MILESTONE",
                {
                    "owner": "schizodactyl",
                    "repo": "kagami",
                    "title": cycle.display_name,
                    "description": f"Linear cycle {cycle.number}",
                    "due_on": cycle.ends_at,
                },
            )

            logger.info(f"✅ Synced cycle {cycle.display_name} to GitHub milestone")
            return True

        except Exception as e:
            logger.error(f"Failed to sync cycle to milestone: {e}")
            return False

    # =========================================================================
    # STATUS
    # =========================================================================

    def get_status(self) -> dict[str, Any]:
        """Get sync status summary."""
        return {
            "initialized": self._initialized,
            "team_key": self.team_key,
            "team_id": self._team_id,
            "cached_cycles": len(self._cycles),
            "cached_issues": len(self._issues),
            "velocity_history": len(self._velocity_history),
            "average_velocity": self.get_average_velocity(),
        }


# =============================================================================
# SINGLETON
# =============================================================================

_linear_sync: LinearSprintSync | None = None


def get_linear_sync() -> LinearSprintSync:
    """Get the global Linear sprint sync instance."""
    global _linear_sync
    if _linear_sync is None:
        _linear_sync = LinearSprintSync()
    return _linear_sync


async def initialize_linear_sync() -> LinearSprintSync:
    """Initialize and return the global Linear sprint sync."""
    sync = get_linear_sync()
    await sync.initialize()
    return sync


__all__ = [
    "CycleInfo",
    "IssueInfo",
    "IssuePriority",
    "IssueState",
    "LinearSprintSync",
    "SprintReport",
    "VelocityMetrics",
    "get_linear_sync",
    "initialize_linear_sync",
]
