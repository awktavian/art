"""Self-healing design violation detection and auto-fix.

This module provides automated design QA through VLM analysis,
creating Linear issues for violations and posting fix suggestions
back to Figma comments.

Pipeline:
1. Detect @design-qa comments in Figma
2. Run VLM analysis on referenced frame
3. Create Linear issue if violations found
4. Post analysis results back to Figma comment
5. Track resolution in stigmergy memory

Integration Points:
- Figma: Read comments, post replies, export images
- Linear: Create issues, track fixes
- VLM: Design analysis via Gemini
- Stigmergy: Learn from resolutions

Created: January 5, 2026
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class DesignViolation:
    """A detected design violation.

    Attributes:
        frame_id: Figma node ID of the violating frame.
        file_key: Figma file key.
        violation_type: Category of violation (accessibility, prismorphism, etc.).
        severity: Severity level (critical, warning, info).
        message: Human-readable description.
        suggestion: Fix suggestion.
    """

    frame_id: str
    file_key: str
    violation_type: str
    severity: str
    message: str
    suggestion: str = ""


@dataclass
class HealingAction:
    """An action taken to heal a violation.

    Attributes:
        violation: The violation being addressed.
        linear_issue_id: Created Linear issue ID.
        figma_comment_id: Posted Figma comment ID.
        status: Current status (pending, in_progress, resolved).
        created_at: When the action was created.
    """

    violation: DesignViolation
    linear_issue_id: str | None = None
    figma_comment_id: str | None = None
    status: str = "pending"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class DesignQASelfHealer:
    """Self-healing system for design QA violations.

    This class detects design violations via VLM analysis,
    creates tracking issues, and posts fix suggestions.

    Attributes:
        team_id: Linear team ID for issue creation.
        design_file_key: Primary Figma design system file.
        auto_create_issues: Whether to automatically create Linear issues.
        min_severity: Minimum severity level to create issues for.

    Example:
        healer = DesignQASelfHealer()
        await healer.initialize()
        violations = await healer.scan_figma_file("27pdTgOq30LHZuaeVYtkEN")
        for v in violations:
            await healer.auto_create_issue(v)
    """

    # Linear team ID (Awkronos)
    DEFAULT_TEAM_ID = "e0d50215-abaa-452a-b2c4-791869719633"

    # Figma design system file
    DEFAULT_DESIGN_FILE = "27pdTgOq30LHZuaeVYtkEN"

    # Self-improvement label ID
    SELF_IMPROVEMENT_LABEL = "self-improvement"

    def __init__(
        self,
        team_id: str | None = None,
        design_file_key: str | None = None,
        auto_create_issues: bool = True,
        min_severity: str = "warning",
    ) -> None:
        """Initialize the self-healer.

        Args:
            team_id: Linear team ID. Defaults to Awkronos.
            design_file_key: Figma file key. Defaults to Kagami Design System.
            auto_create_issues: Whether to auto-create issues.
            min_severity: Minimum severity for issue creation.
        """
        self.team_id = team_id or self.DEFAULT_TEAM_ID
        self.design_file_key = design_file_key or self.DEFAULT_DESIGN_FILE
        self.auto_create_issues = auto_create_issues
        self.min_severity = min_severity

        self._figma_client = None
        self._composio_service = None
        self._initialized = False
        self._actions: list[HealingAction] = []

    async def initialize(self) -> None:
        """Initialize connections to Figma, Linear, and VLM."""
        if self._initialized:
            return

        try:
            from kagami.core.integrations.figma_direct import get_figma_client
            from kagami.core.services.composio import get_composio_service

            self._figma_client = await get_figma_client()
            self._composio_service = get_composio_service()
            await self._composio_service.initialize()

            self._initialized = True
            logger.info("DesignQASelfHealer initialized")

        except Exception as e:
            logger.error(f"Self-healer initialization failed: {e}")
            raise

    async def scan_figma_file(
        self,
        file_key: str | None = None,
    ) -> list[DesignViolation]:
        """Scan a Figma file for design violations.

        Uses VLM analysis on each page/frame to detect violations.

        Args:
            file_key: Figma file key. Defaults to design system.

        Returns:
            List of detected violations.
        """
        if not self._initialized:
            await self.initialize()

        file_key = file_key or self.design_file_key
        violations: list[DesignViolation] = []

        try:
            # Get file structure
            file_data = await self._figma_client.get_file(file_key, depth=2)
            document = file_data.get("document", {})

            # Analyze each page
            for page in document.get("children", []):
                page_violations = await self._analyze_page(file_key, page)
                violations.extend(page_violations)

            logger.info(f"Scan complete: {len(violations)} violations found")

        except Exception as e:
            logger.error(f"File scan failed: {e}")

        return violations

    async def _analyze_page(
        self,
        file_key: str,
        page: dict[str, Any],
    ) -> list[DesignViolation]:
        """Analyze a single page for violations.

        Args:
            file_key: Figma file key.
            page: Page data from Figma API.

        Returns:
            List of violations found on this page.
        """
        violations = []
        page.get("name", "Unknown")

        # Get main frames (first level children)
        for frame in page.get("children", [])[:5]:  # Limit to 5 frames per page
            frame_id = frame.get("id")
            frame_name = frame.get("name", "Unknown")

            if not frame_id:
                continue

            try:
                from kagami.core.integrations.figma_vlm import analyze_figma_frame

                result = await analyze_figma_frame(file_key, frame_id)

                # Convert VLM result to violations
                if result.score < 60:
                    for violation_msg in result.violations:
                        violations.append(
                            DesignViolation(
                                frame_id=frame_id,
                                file_key=file_key,
                                violation_type="design",
                                severity="critical" if result.score < 40 else "warning",
                                message=violation_msg,
                                suggestion=result.suggestions[0] if result.suggestions else "",
                            )
                        )

                # Add accessibility issues
                for a11y_issue in result.accessibility_issues:
                    violations.append(
                        DesignViolation(
                            frame_id=frame_id,
                            file_key=file_key,
                            violation_type="accessibility",
                            severity="critical",
                            message=a11y_issue,
                        )
                    )

                # Add prismorphism compliance issue if below threshold
                if result.prismorphism_compliance < 0.8:
                    violations.append(
                        DesignViolation(
                            frame_id=frame_id,
                            file_key=file_key,
                            violation_type="prismorphism",
                            severity="warning",
                            message=f"Prismorphism compliance: {result.prismorphism_compliance:.0%}",
                            suggestion="Review spectral colors and glassmorphism effects",
                        )
                    )

            except Exception as e:
                logger.debug(f"Frame analysis failed for {frame_name}: {e}")

        return violations

    async def auto_create_issue(
        self,
        violation: DesignViolation,
    ) -> HealingAction | None:
        """Create a Linear issue for a violation.

        Args:
            violation: The violation to create an issue for.

        Returns:
            HealingAction with issue details, or None if creation failed.
        """
        if not self._initialized:
            await self.initialize()

        # Check severity threshold
        severity_levels = {"info": 0, "warning": 1, "critical": 2}
        if severity_levels.get(violation.severity, 0) < severity_levels.get(self.min_severity, 1):
            logger.debug(f"Skipping {violation.severity} violation (below threshold)")
            return None

        try:
            # Create Linear issue
            title = f"[Design QA] {violation.violation_type.title()}: {violation.message[:50]}"
            description = f"""**Automated Design QA Detection**

**File:** {violation.file_key}
**Frame:** {violation.frame_id}
**Type:** {violation.violation_type}
**Severity:** {violation.severity}

**Issue:**
{violation.message}

**Suggestion:**
{violation.suggestion or "Manual review recommended"}

---
*Created by Kagami Design QA Self-Healer*
"""

            result = await self._composio_service.execute_action(
                "LINEAR_CREATE_LINEAR_ISSUE",
                {
                    "team_id": self.team_id,
                    "title": title,
                    "description": description,
                    "priority": 1 if violation.severity == "critical" else 2,
                },
            )

            if result.get("successful"):
                issue_data = result.get("data", {})
                issue_id = issue_data.get("id") or issue_data.get("issueCreate", {}).get(
                    "issue", {}
                ).get("id")

                action = HealingAction(
                    violation=violation,
                    linear_issue_id=issue_id,
                    status="in_progress",
                )
                self._actions.append(action)

                logger.info(f"Created Linear issue: {issue_id}")

                # Post Figma comment
                await self._post_figma_comment(action)

                return action

        except Exception as e:
            logger.error(f"Issue creation failed: {e}")

        return None

    async def _post_figma_comment(self, action: HealingAction) -> None:
        """Post analysis results back to Figma as a comment.

        Args:
            action: The healing action with violation details.
        """
        try:
            v = action.violation
            message = f"""🔍 **Design QA Analysis**

**Issue:** {v.message}
**Type:** {v.violation_type}
**Severity:** {v.severity}

**Tracking:** Linear issue created
"""
            if v.suggestion:
                message += f"\n**Suggestion:** {v.suggestion}"

            await self._figma_client.add_comment(
                v.file_key,
                message,
                node_id=v.frame_id,
            )

            logger.info(f"Posted Figma comment for frame {v.frame_id}")

        except Exception as e:
            logger.debug(f"Figma comment failed: {e}")

    async def process_design_qa_comment(
        self,
        file_key: str,
        comment: dict[str, Any],
    ) -> HealingAction | None:
        """Process a @design-qa comment trigger.

        This is called when a Figma comment contains @design-qa.
        It analyzes the referenced frame and creates issues if needed.

        Args:
            file_key: Figma file key.
            comment: Comment data from Figma API.

        Returns:
            HealingAction if issues were created, None otherwise.
        """
        try:
            from kagami.core.integrations.figma_vlm import analyze_design_comment

            result = await analyze_design_comment(file_key, comment)

            if result and result.score < 80:
                # Create violation from analysis
                violation = DesignViolation(
                    frame_id=comment.get("client_meta", {}).get("node_id", ""),
                    file_key=file_key,
                    violation_type="design_qa_triggered",
                    severity="warning" if result.score >= 60 else "critical",
                    message="; ".join(result.violations[:3]),
                    suggestion="; ".join(result.suggestions[:2]),
                )

                # Reply to the original comment with results
                reply = result.to_comment()
                await self._figma_client.add_comment(
                    file_key,
                    reply,
                    reply_to=comment.get("id"),
                )

                # Create issue if auto-create is enabled
                if self.auto_create_issues:
                    return await self.auto_create_issue(violation)

        except Exception as e:
            logger.error(f"Design QA comment processing failed: {e}")

        return None

    def get_actions(self) -> list[HealingAction]:
        """Get all healing actions taken.

        Returns:
            List of HealingAction objects.
        """
        return list(self._actions)

    def get_pending_actions(self) -> list[HealingAction]:
        """Get pending healing actions.

        Returns:
            List of pending HealingAction objects.
        """
        return [a for a in self._actions if a.status == "pending"]


# Singleton instance
_healer: DesignQASelfHealer | None = None


async def get_design_qa_healer() -> DesignQASelfHealer:
    """Get or create the global DesignQASelfHealer instance.

    Returns:
        Initialized DesignQASelfHealer.
    """
    global _healer
    if _healer is None:
        _healer = DesignQASelfHealer()
        await _healer.initialize()
    return _healer
