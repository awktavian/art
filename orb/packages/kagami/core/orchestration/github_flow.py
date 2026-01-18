"""GitHub Development Flow — Automated Branch and PR Management.

This module provides automated development workflows using GitHub:
- Auto-create feature branches from Linear issues
- Track PR status and sync to Linear
- Trigger CI workflows and parse results
- Auto-merge when all checks pass

Architecture:
    ┌────────────────────────────────────────────────────────────────────────┐
    │                     GITHUB DEVELOPMENT FLOW                             │
    │                                                                        │
    │  Linear Issue ──► Create Branch ──► Development ──► Create PR          │
    │       │                                                │                │
    │       │                                                ▼                │
    │       │                                          CI Workflows          │
    │       │                                                │                │
    │       ▼                                                ▼                │
    │  Update Issue ◄─── Sync Status ◄─── Check Results ◄── Pass?           │
    │       │                                                │                │
    │       │                                    Yes ────────┘                │
    │       ▼                                                                 │
    │  Close Issue ◄───────────────── Auto-Merge PR                          │
    └────────────────────────────────────────────────────────────────────────┘

Usage:
    from kagami.core.orchestration.github_flow import get_github_flow

    flow = await get_github_flow()

    # Create branch from Linear issue
    branch = await flow.create_branch_from_issue(issue_id="KAG-123")

    # Create PR and track
    pr = await flow.create_pr_for_branch(branch_name="feature/KAG-123-my-feature")

    # Auto-merge when ready
    await flow.auto_merge_when_ready(pr_number=42)
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kagami.core.services.composio import ComposioIntegrationService

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

# Default repository settings
DEFAULT_OWNER = "schizodactyl"
DEFAULT_REPO = "kagami"
DEFAULT_BASE_BRANCH = "main"


class PRStatus(Enum):
    """Pull request status."""

    DRAFT = "draft"
    OPEN = "open"
    REVIEW_REQUIRED = "review_required"
    CHANGES_REQUESTED = "changes_requested"
    APPROVED = "approved"
    CHECKS_PENDING = "checks_pending"
    CHECKS_FAILED = "checks_failed"
    CHECKS_PASSED = "checks_passed"
    MERGED = "merged"
    CLOSED = "closed"


class CIStatus(Enum):
    """CI workflow status."""

    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    WAITING = "waiting"
    REQUESTED = "requested"
    PENDING = "pending"


class CIConclusion(Enum):
    """CI workflow conclusion."""

    SUCCESS = "success"
    FAILURE = "failure"
    NEUTRAL = "neutral"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"
    TIMED_OUT = "timed_out"
    ACTION_REQUIRED = "action_required"
    STALE = "stale"


@dataclass
class BranchInfo:
    """Information about a Git branch."""

    name: str
    ref: str  # Full ref (refs/heads/branch-name)
    sha: str  # Commit SHA
    created_at: float = field(default_factory=time.time)
    linear_issue_id: str | None = None

    @property
    def short_ref(self) -> str:
        """Get short ref without refs/heads/ prefix."""
        return self.name


@dataclass
class PRInfo:
    """Information about a Pull Request."""

    number: int
    title: str
    body: str
    state: str
    html_url: str
    head_branch: str
    base_branch: str
    draft: bool = False
    mergeable: bool | None = None
    merged: bool = False
    linear_issue_id: str | None = None
    ci_status: CIStatus | None = None
    ci_conclusion: CIConclusion | None = None

    @property
    def status(self) -> PRStatus:
        """Compute PR status from state and checks."""
        if self.merged:
            return PRStatus.MERGED
        if self.state == "closed":
            return PRStatus.CLOSED
        if self.draft:
            return PRStatus.DRAFT
        if self.ci_status == CIStatus.IN_PROGRESS:
            return PRStatus.CHECKS_PENDING
        if self.ci_conclusion == CIConclusion.FAILURE:
            return PRStatus.CHECKS_FAILED
        if self.ci_conclusion == CIConclusion.SUCCESS:
            return PRStatus.CHECKS_PASSED
        return PRStatus.OPEN


@dataclass
class WorkflowRun:
    """Information about a CI workflow run."""

    id: int
    name: str
    status: CIStatus
    conclusion: CIConclusion | None
    html_url: str
    created_at: str
    head_sha: str


# =============================================================================
# GITHUB DEVELOPMENT FLOW
# =============================================================================


class GitHubDevelopmentFlow:
    """Automated GitHub development workflow manager.

    This class provides high-level operations for managing development workflows:

    1. Branch Creation: Auto-create feature branches from Linear issues
    2. PR Management: Create and track pull requests
    3. CI Integration: Monitor workflow runs and check status
    4. Auto-Merge: Automatically merge PRs when all checks pass
    5. Linear Sync: Keep Linear issues updated with PR status

    All operations use the Composio GitHub integration for API calls.
    """

    def __init__(
        self,
        owner: str = DEFAULT_OWNER,
        repo: str = DEFAULT_REPO,
        base_branch: str = DEFAULT_BASE_BRANCH,
    ) -> None:
        """Initialize GitHub development flow.

        Args:
            owner: Repository owner
            repo: Repository name
            base_branch: Default base branch for PRs
        """
        self.owner = owner
        self.repo = repo
        self.base_branch = base_branch

        self._composio: ComposioIntegrationService | None = None
        self._initialized = False

        # Track active branches and PRs
        self._branches: dict[str, BranchInfo] = {}
        self._prs: dict[int, PRInfo] = {}

        # Auto-merge queue
        self._auto_merge_queue: set[int] = set()
        self._merge_check_task: asyncio.Task[None] | None = None

    async def initialize(self) -> bool:
        """Initialize the GitHub flow.

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
                logger.warning("Composio not initialized - GitHub flow disabled")
                return False

            # Verify GitHub is connected
            apps = await self._composio.get_connected_apps()
            github_connected = any(app.get("toolkit") == "github" for app in apps)

            if not github_connected:
                logger.warning("GitHub not connected to Composio - run 'composio add github'")
                return False

            self._initialized = True
            logger.info(f"✅ GitHubDevelopmentFlow initialized: {self.owner}/{self.repo}")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize GitHubDevelopmentFlow: {e}")
            return False

    # =========================================================================
    # BRANCH MANAGEMENT
    # =========================================================================

    async def create_branch(
        self,
        branch_name: str,
        from_ref: str | None = None,
        linear_issue_id: str | None = None,
    ) -> BranchInfo | None:
        """Create a new branch.

        Args:
            branch_name: Name for the new branch
            from_ref: Base ref to branch from (default: base_branch)
            linear_issue_id: Optional Linear issue ID to associate

        Returns:
            BranchInfo if successful, None otherwise
        """
        await self.initialize()

        if not self._composio:
            return None

        try:
            # Get SHA of base ref
            base_ref = from_ref or self.base_branch

            # Get the reference to branch from
            ref_result = await self._composio.execute_action(
                "GITHUB_GET_A_REFERENCE",
                {
                    "owner": self.owner,
                    "repo": self.repo,
                    "ref": f"heads/{base_ref}",
                },
            )

            base_sha = ref_result.get("data", {}).get("object", {}).get("sha")
            if not base_sha:
                logger.error(f"Could not get SHA for {base_ref}")
                return None

            # Create the new branch
            result = await self._composio.execute_action(
                "GITHUB_CREATE_A_REFERENCE",
                {
                    "owner": self.owner,
                    "repo": self.repo,
                    "ref": f"refs/heads/{branch_name}",
                    "sha": base_sha,
                },
            )

            if not result.get("success", True):
                logger.error(f"Failed to create branch: {result}")
                return None

            branch_info = BranchInfo(
                name=branch_name,
                ref=f"refs/heads/{branch_name}",
                sha=base_sha,
                linear_issue_id=linear_issue_id,
            )

            self._branches[branch_name] = branch_info
            logger.info(f"✅ Created branch: {branch_name}")

            return branch_info

        except Exception as e:
            logger.error(f"Failed to create branch {branch_name}: {e}")
            return None

    async def create_branch_from_issue(
        self,
        issue_id: str,
        branch_prefix: str = "feature",
    ) -> BranchInfo | None:
        """Create a branch from a Linear issue.

        Args:
            issue_id: Linear issue ID (e.g., "KAG-123")
            branch_prefix: Prefix for branch name (feature, fix, etc.)

        Returns:
            BranchInfo if successful, None otherwise
        """
        await self.initialize()

        if not self._composio:
            return None

        try:
            # Get Linear issue details
            result = await self._composio.execute_action(
                "LINEAR_GET_LINEAR_ISSUE", {"issueId": issue_id}
            )

            issue_data = result.get("data", {}).get("issue", {})
            title = issue_data.get("title", "unknown")

            # Create branch name from issue
            # Sanitize title for branch name
            sanitized = re.sub(r"[^a-zA-Z0-9\s-]", "", title.lower())
            sanitized = re.sub(r"\s+", "-", sanitized)[:50]

            branch_name = f"{branch_prefix}/{issue_id.lower()}-{sanitized}"

            return await self.create_branch(
                branch_name=branch_name,
                linear_issue_id=issue_id,
            )

        except Exception as e:
            logger.error(f"Failed to create branch from issue {issue_id}: {e}")
            return None

    async def delete_branch(self, branch_name: str) -> bool:
        """Delete a branch.

        Args:
            branch_name: Name of branch to delete

        Returns:
            True if deleted successfully
        """
        await self.initialize()

        if not self._composio:
            return False

        try:
            _result = await self._composio.execute_action(
                "GITHUB_DELETE_A_REFERENCE",
                {
                    "owner": self.owner,
                    "repo": self.repo,
                    "ref": f"heads/{branch_name}",
                },
            )

            if branch_name in self._branches:
                del self._branches[branch_name]

            logger.info(f"✅ Deleted branch: {branch_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete branch {branch_name}: {e}")
            return False

    # =========================================================================
    # PULL REQUEST MANAGEMENT
    # =========================================================================

    async def create_pr(
        self,
        title: str,
        head: str,
        body: str = "",
        base: str | None = None,
        draft: bool = False,
        linear_issue_id: str | None = None,
    ) -> PRInfo | None:
        """Create a pull request.

        Args:
            title: PR title
            head: Head branch name
            body: PR description
            base: Base branch (default: base_branch)
            draft: Create as draft PR
            linear_issue_id: Optional Linear issue to link

        Returns:
            PRInfo if successful, None otherwise
        """
        await self.initialize()

        if not self._composio:
            return None

        try:
            # Add Linear issue link to body if provided
            if linear_issue_id:
                body = f"{body}\n\nLinear: {linear_issue_id}"

            result = await self._composio.execute_action(
                "GITHUB_CREATE_A_PULL_REQUEST",
                {
                    "owner": self.owner,
                    "repo": self.repo,
                    "title": title,
                    "head": head,
                    "base": base or self.base_branch,
                    "body": body,
                    "draft": draft,
                },
            )

            pr_data = result.get("data", {})
            if not pr_data.get("number"):
                logger.error(f"Failed to create PR: {result}")
                return None

            pr_info = PRInfo(
                number=pr_data["number"],
                title=pr_data.get("title", title),
                body=pr_data.get("body", body),
                state=pr_data.get("state", "open"),
                html_url=pr_data.get("html_url", ""),
                head_branch=head,
                base_branch=base or self.base_branch,
                draft=pr_data.get("draft", draft),
                linear_issue_id=linear_issue_id,
            )

            self._prs[pr_info.number] = pr_info
            logger.info(f"✅ Created PR #{pr_info.number}: {title}")

            # Update Linear issue if linked
            if linear_issue_id:
                await self._update_linear_issue_with_pr(linear_issue_id, pr_info)

            return pr_info

        except Exception as e:
            logger.error(f"Failed to create PR: {e}")
            return None

    async def create_pr_for_branch(
        self,
        branch_name: str,
        title: str | None = None,
        body: str = "",
        draft: bool = False,
    ) -> PRInfo | None:
        """Create a PR for an existing branch.

        Args:
            branch_name: Name of the head branch
            title: PR title (auto-generated from branch if None)
            body: PR description
            draft: Create as draft PR

        Returns:
            PRInfo if successful, None otherwise
        """
        # Get branch info if we have it
        branch_info = self._branches.get(branch_name)
        linear_issue_id = branch_info.linear_issue_id if branch_info else None

        # Auto-generate title from branch name if not provided
        if title is None:
            # Convert feature/kag-123-my-feature to "KAG-123: My feature"
            parts = branch_name.split("/", 1)
            name_part = parts[-1]

            # Extract issue ID if present
            match = re.match(r"([a-zA-Z]+-\d+)-?(.+)?", name_part)
            if match:
                issue_id = match.group(1).upper()
                description = match.group(2) or ""
                description = description.replace("-", " ").title()
                title = f"{issue_id}: {description}".strip(": ")
            else:
                title = name_part.replace("-", " ").title()

        return await self.create_pr(
            title=title,
            head=branch_name,
            body=body,
            draft=draft,
            linear_issue_id=linear_issue_id,
        )

    async def get_pr(self, pr_number: int) -> PRInfo | None:
        """Get PR information.

        Args:
            pr_number: PR number

        Returns:
            PRInfo if found, None otherwise
        """
        await self.initialize()

        if not self._composio:
            return None

        try:
            result = await self._composio.execute_action(
                "GITHUB_GET_A_PULL_REQUEST",
                {
                    "owner": self.owner,
                    "repo": self.repo,
                    "pull_number": pr_number,
                },
            )

            pr_data = result.get("data", {})
            if not pr_data:
                return None

            pr_info = PRInfo(
                number=pr_data["number"],
                title=pr_data.get("title", ""),
                body=pr_data.get("body", ""),
                state=pr_data.get("state", "unknown"),
                html_url=pr_data.get("html_url", ""),
                head_branch=pr_data.get("head", {}).get("ref", ""),
                base_branch=pr_data.get("base", {}).get("ref", ""),
                draft=pr_data.get("draft", False),
                mergeable=pr_data.get("mergeable"),
                merged=pr_data.get("merged", False),
            )

            # Get CI status
            ci_status = await self._get_ci_status_for_pr(pr_info)
            if ci_status:
                pr_info.ci_status = ci_status.get("status")
                pr_info.ci_conclusion = ci_status.get("conclusion")

            self._prs[pr_number] = pr_info
            return pr_info

        except Exception as e:
            logger.error(f"Failed to get PR #{pr_number}: {e}")
            return None

    async def merge_pr(
        self,
        pr_number: int,
        merge_method: str = "squash",
        commit_title: str | None = None,
        commit_message: str | None = None,
    ) -> bool:
        """Merge a pull request.

        Args:
            pr_number: PR number to merge
            merge_method: Merge method (merge, squash, rebase)
            commit_title: Custom commit title
            commit_message: Custom commit message

        Returns:
            True if merged successfully
        """
        await self.initialize()

        if not self._composio:
            return False

        try:
            params: dict[str, Any] = {
                "owner": self.owner,
                "repo": self.repo,
                "pull_number": pr_number,
                "merge_method": merge_method,
            }

            if commit_title:
                params["commit_title"] = commit_title
            if commit_message:
                params["commit_message"] = commit_message

            result = await self._composio.execute_action(
                "GITHUB_MERGE_A_PULL_REQUEST",
                params,
            )

            if result.get("data", {}).get("merged"):
                logger.info(f"✅ Merged PR #{pr_number}")

                # Update cached PR info
                if pr_number in self._prs:
                    self._prs[pr_number].merged = True

                # Update Linear issue if linked
                pr_info = self._prs.get(pr_number)
                if pr_info and pr_info.linear_issue_id:
                    await self._complete_linear_issue(pr_info.linear_issue_id)

                return True

            logger.warning(f"PR #{pr_number} not merged: {result}")
            return False

        except Exception as e:
            logger.error(f"Failed to merge PR #{pr_number}: {e}")
            return False

    # =========================================================================
    # CI INTEGRATION
    # =========================================================================

    async def get_workflow_runs(
        self,
        branch: str | None = None,
        status: str | None = None,
        limit: int = 10,
    ) -> list[WorkflowRun]:
        """Get workflow runs for the repository.

        Args:
            branch: Filter by branch
            status: Filter by status
            limit: Maximum number of runs to return

        Returns:
            List of WorkflowRun objects
        """
        await self.initialize()

        if not self._composio:
            return []

        try:
            params: dict[str, Any] = {
                "owner": self.owner,
                "repo": self.repo,
                "per_page": limit,
            }

            if branch:
                params["branch"] = branch
            if status:
                params["status"] = status

            result = await self._composio.execute_action(
                "GITHUB_LIST_WORKFLOW_RUNS_FOR_A_REPOSITORY",
                params,
            )

            runs_data = result.get("data", {}).get("workflow_runs", [])

            runs = []
            for run in runs_data:
                try:
                    status_val = CIStatus(run.get("status", "pending"))
                except ValueError:
                    status_val = CIStatus.PENDING

                conclusion_val = None
                if run.get("conclusion"):
                    try:
                        conclusion_val = CIConclusion(run["conclusion"])
                    except ValueError:
                        pass

                runs.append(
                    WorkflowRun(
                        id=run["id"],
                        name=run.get("name", ""),
                        status=status_val,
                        conclusion=conclusion_val,
                        html_url=run.get("html_url", ""),
                        created_at=run.get("created_at", ""),
                        head_sha=run.get("head_sha", ""),
                    )
                )

            return runs

        except Exception as e:
            logger.error(f"Failed to get workflow runs: {e}")
            return []

    async def _get_ci_status_for_pr(
        self,
        pr_info: PRInfo,
    ) -> dict[str, Any] | None:
        """Get CI status for a PR.

        Args:
            pr_info: PR information

        Returns:
            Dict with status and conclusion, or None
        """
        runs = await self.get_workflow_runs(branch=pr_info.head_branch, limit=5)

        if not runs:
            return None

        # Get the most recent run
        latest_run = runs[0]

        return {
            "status": latest_run.status,
            "conclusion": latest_run.conclusion,
        }

    # =========================================================================
    # AUTO-MERGE
    # =========================================================================

    async def auto_merge_when_ready(
        self,
        pr_number: int,
        merge_method: str = "squash",
    ) -> None:
        """Add PR to auto-merge queue.

        The PR will be automatically merged when all checks pass.

        Args:
            pr_number: PR number to auto-merge
            merge_method: Merge method to use
        """
        self._auto_merge_queue.add(pr_number)
        logger.info(f"✅ Added PR #{pr_number} to auto-merge queue")

        # Start the merge check task if not running
        if self._merge_check_task is None or self._merge_check_task.done():
            self._merge_check_task = asyncio.create_task(self._merge_check_loop())

    async def _merge_check_loop(self) -> None:
        """Background loop to check and merge ready PRs."""
        while self._auto_merge_queue:
            try:
                for pr_number in list(self._auto_merge_queue):
                    pr_info = await self.get_pr(pr_number)

                    if pr_info is None:
                        self._auto_merge_queue.discard(pr_number)
                        continue

                    if pr_info.merged or pr_info.state == "closed":
                        self._auto_merge_queue.discard(pr_number)
                        continue

                    if pr_info.status == PRStatus.CHECKS_PASSED:
                        if await self.merge_pr(pr_number):
                            self._auto_merge_queue.discard(pr_number)

                await asyncio.sleep(60)  # Check every minute

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Merge check loop error: {e}")
                await asyncio.sleep(60)

    # =========================================================================
    # LINEAR INTEGRATION
    # =========================================================================

    async def _update_linear_issue_with_pr(
        self,
        issue_id: str,
        pr_info: PRInfo,
    ) -> None:
        """Update a Linear issue with PR information.

        Args:
            issue_id: Linear issue ID
            pr_info: PR information
        """
        if not self._composio:
            return

        try:
            # Add comment with PR link
            await self._composio.execute_action(
                "LINEAR_CREATE_A_COMMENT",
                {
                    "issueId": issue_id,
                    "body": f"🔗 PR Created: [{pr_info.title}]({pr_info.html_url})",
                },
            )

            logger.debug(f"Updated Linear issue {issue_id} with PR #{pr_info.number}")

        except Exception as e:
            logger.warning(f"Failed to update Linear issue {issue_id}: {e}")

    async def _complete_linear_issue(self, issue_id: str) -> None:
        """Mark a Linear issue as complete.

        Args:
            issue_id: Linear issue ID
        """
        if not self._composio:
            return

        try:
            # Get done state ID
            # For now, just add a comment - state change requires knowing state IDs
            await self._composio.execute_action(
                "LINEAR_CREATE_A_COMMENT",
                {
                    "issueId": issue_id,
                    "body": "✅ PR Merged - Issue complete!",
                },
            )

            logger.debug(f"Marked Linear issue {issue_id} as complete")

        except Exception as e:
            logger.warning(f"Failed to complete Linear issue {issue_id}: {e}")

    # =========================================================================
    # STATUS
    # =========================================================================

    def get_status(self) -> dict[str, Any]:
        """Get flow status summary."""
        return {
            "initialized": self._initialized,
            "repo": f"{self.owner}/{self.repo}",
            "base_branch": self.base_branch,
            "tracked_branches": len(self._branches),
            "tracked_prs": len(self._prs),
            "auto_merge_queue": list(self._auto_merge_queue),
            "merge_check_active": (
                self._merge_check_task is not None and not self._merge_check_task.done()
            ),
        }


# =============================================================================
# SINGLETON
# =============================================================================

_github_flow: GitHubDevelopmentFlow | None = None


def get_github_flow() -> GitHubDevelopmentFlow:
    """Get the global GitHub development flow instance."""
    global _github_flow
    if _github_flow is None:
        _github_flow = GitHubDevelopmentFlow()
    return _github_flow


async def initialize_github_flow() -> GitHubDevelopmentFlow:
    """Initialize and return the global GitHub development flow."""
    flow = get_github_flow()
    await flow.initialize()
    return flow


__all__ = [
    "BranchInfo",
    "CIConclusion",
    "CIStatus",
    "GitHubDevelopmentFlow",
    "PRInfo",
    "PRStatus",
    "WorkflowRun",
    "get_github_flow",
    "initialize_github_flow",
]
