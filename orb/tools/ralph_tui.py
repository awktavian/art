#!/usr/bin/env python3
"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                    PARALLEL RALPH TUI — Byzantine Consensus                   ║
║                                                                               ║
║  Animated real-time visualization of parallel agent execution                ║
║  with Byzantine fault-tolerant consensus voting.                             ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

import asyncio
import re
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from rich.align import Align
from rich.box import HEAVY, ROUNDED
from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.style import Style
from rich.table import Table
from rich.text import Text


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════


class LaneStatus(Enum):
    """Lane execution status with personality."""

    IDLE = ("⚪", "dim white", "Waiting...")
    STARTING = ("🔵", "bright_blue", "Spinning up...")
    RUNNING = ("🟢", "bright_green", "Crushing it")
    THINKING = ("🟡", "yellow", "Deep in thought")
    CONSENSUS = ("🟣", "magenta", "Voting...")
    SUCCESS = ("✅", "green", "Nailed it")
    WARNING = ("⚠️", "yellow", "Hmm, interesting")
    ERROR = ("❌", "red", "Well, that's awkward")
    COMPLETE = ("🎉", "cyan", "Mission accomplished")


@dataclass
class AgentWindow:
    """Animated agent window with momentum."""

    name: str
    x: float
    y: float
    vx: float = 0.0  # velocity x
    vy: float = 0.0  # velocity y
    status: LaneStatus = LaneStatus.IDLE
    score: int = 0
    message: str = ""
    vote: bool | None = None  # Byzantine vote
    last_update: float = field(default_factory=time.time)

    def update_physics(self, dt: float, width: int, height: int) -> None:
        """Update position with physics and boundary bouncing."""
        # Apply velocity
        self.x += self.vx * dt
        self.y += self.vy * dt

        # Bounce off walls with damping
        if self.x <= 0 or self.x >= width - 20:
            self.vx *= -0.8
            self.x = max(0, min(width - 20, self.x))

        if self.y <= 0 or self.y >= height - 8:
            self.vy *= -0.8
            self.y = max(0, min(height - 8, self.y))

        # Friction
        self.vx *= 0.98
        self.vy *= 0.98


@dataclass
class ByzantineVote:
    """Byzantine consensus vote."""

    agent: str
    vote: bool
    score: int
    timestamp: float = field(default_factory=time.time)


@dataclass
class ConsensusRound:
    """Byzantine consensus round."""

    round_id: int
    phase: str = "PRE_VOTE"
    votes: list[ByzantineVote] = field(default_factory=list)
    quorum: int = 5  # 2f+1 for 7 agents
    threshold: float = 70.0

    def add_vote(self, agent: str, vote: bool, score: int) -> None:
        """Add agent vote."""
        self.votes.append(ByzantineVote(agent, vote, score))

    def has_consensus(self) -> bool:
        """Check if consensus reached."""
        if len(self.votes) < self.quorum:
            return False
        approve = sum(1 for v in self.votes if v.vote)
        return approve >= self.quorum

    def get_result(self) -> tuple[bool, float]:
        """Get consensus result."""
        if not self.votes:
            return False, 0.0
        approve = sum(1 for v in self.votes if v.vote)
        avg_score = sum(v.score for v in self.votes) / len(self.votes)
        return approve >= self.quorum, avg_score


# ═══════════════════════════════════════════════════════════════════════════════
# TUI RENDERER
# ═══════════════════════════════════════════════════════════════════════════════


class ParallelRalphTUI:
    """Animated TUI for parallel Ralph execution."""

    # Color palette
    COLORS = {
        "primary": "#7E57C2",  # Deep purple
        "success": "#4CAF50",  # Green
        "warning": "#FF9800",  # Orange
        "error": "#F44336",  # Red
        "info": "#2196F3",  # Blue
        "accent": "#E91E63",  # Pink
        "text": "#ECEFF1",  # Light gray
        "muted": "#78909C",  # Blue gray
        "bg": "#1A1A1A",  # Dark
    }

    def __init__(self, log_dir: Path):
        """Initialize TUI."""
        self.console = Console()
        self.log_dir = log_dir

        # Agent windows (7 for Byzantine consensus)
        self.agents = [
            AgentWindow(
                name=f"Agent {i + 1}",
                x=float((i % 3) * 30 + 10),
                y=float((i // 3) * 10 + 5),
                vx=float((i * 7 % 11) - 5),  # Random initial velocity
                vy=float((i * 13 % 11) - 5),
            )
            for i in range(7)
        ]

        # Consensus state
        self.consensus_round = ConsensusRound(round_id=1)

        # Metrics
        self.metrics = {
            "step": 0,
            "loss": 0.0,
            "phase": "INIT",
            "receipts": 0,
            "validations": 0,
            "uptime": 0.0,
        }

        # Activity log
        self.activity_log = deque(maxlen=10)

        # Start time
        self.start_time = time.time()

    def update_from_logs(self) -> None:
        """Parse logs and update state."""
        # Parse lane logs
        for i, lane in enumerate(["pretrain", "online", "monitor", "validate"]):
            log_file = self.log_dir / f"lane{i + 1}_{lane}.log"
            if log_file.exists():
                self._parse_log(log_file, i)

        # Update uptime
        self.metrics["uptime"] = time.time() - self.start_time

    def _parse_log(self, log_file: Path, agent_idx: int) -> None:
        """Parse log file and update agent."""
        if agent_idx >= len(self.agents):
            return

        agent = self.agents[agent_idx]

        try:
            with open(log_file) as f:
                # Read last 50 lines
                lines = deque(f, maxlen=50)

                for line in lines:
                    # Parse metrics
                    if match := re.search(r"[Ss]tep[:\s]+(\d+)", line):
                        self.metrics["step"] = int(match.group(1))

                    if match := re.search(r"[Ll]oss[:\s]+([0-9.e+-]+)", line):
                        self.metrics["loss"] = float(match.group(1))

                    if match := re.search(r"[Pp]hase[:\s]+(\w+)", line):
                        self.metrics["phase"] = match.group(1)

                    if match := re.search(r"[Rr]eceipts[:\s]+(\d+)", line):
                        self.metrics["receipts"] = int(match.group(1))

                    # Update agent status
                    if "error" in line.lower() or "failed" in line.lower():
                        agent.status = LaneStatus.ERROR
                        agent.message = "Error detected"
                    elif "success" in line.lower() or "passed" in line.lower():
                        agent.status = LaneStatus.SUCCESS
                        agent.message = "Looking good"
                    elif "starting" in line.lower():
                        agent.status = LaneStatus.STARTING
                        agent.message = "Initializing"
                    elif "running" in line.lower() or "step" in line.lower():
                        agent.status = LaneStatus.RUNNING
                        agent.message = "Processing"

                    # Extract score if present
                    if match := re.search(r"[Ss]core[:\s]+(\d+)", line):
                        agent.score = int(match.group(1))

                agent.last_update = time.time()

        except Exception as e:
            agent.status = LaneStatus.ERROR
            agent.message = f"Log error: {str(e)[:30]}"

    def update_consensus(self) -> None:
        """Update Byzantine consensus state."""
        # Simulate voting based on agent scores
        for agent in self.agents:
            if agent.vote is None and agent.score > 0:
                # Agent votes based on score threshold
                vote = agent.score >= self.consensus_round.threshold
                agent.vote = vote
                self.consensus_round.add_vote(agent.name, vote, agent.score)

                # Log vote
                vote_str = "✓ APPROVE" if vote else "✗ REJECT"
                self.activity_log.append(f"{agent.name}: {vote_str} (score: {agent.score})")

        # Check consensus
        if self.consensus_round.has_consensus():
            self.consensus_round.phase = "COMMIT"
            result, avg_score = self.consensus_round.get_result()
            self.activity_log.append(
                f"🎯 CONSENSUS: {'APPROVED' if result else 'REJECTED'} (avg: {avg_score:.1f})"
            )

    def render_header(self) -> Panel:
        """Render animated header."""
        # Animated title with gradient
        title = Text()
        title.append("╔═══════════════════════════════════════════╗\n", style="bold magenta")
        title.append("║  ", style="bold magenta")
        title.append("PARALLEL RALPH", style=f"bold {self.COLORS['primary']}")
        title.append(" — ", style="dim")
        title.append("Byzantine Consensus", style=f"bold {self.COLORS['accent']}")
        title.append("  ║\n", style="bold magenta")
        title.append("╚═══════════════════════════════════════════╝", style="bold magenta")

        # Uptime with personality
        uptime_mins = int(self.metrics["uptime"] / 60)
        uptime_secs = int(self.metrics["uptime"] % 60)

        subtitle = Text()
        subtitle.append("⏱️  Uptime: ", style="dim")
        subtitle.append(f"{uptime_mins}m {uptime_secs}s", style="bold cyan")
        subtitle.append("  •  ", style="dim")
        subtitle.append("Step: ", style="dim")
        subtitle.append(f"{self.metrics['step']:,}", style="bold yellow")
        subtitle.append("  •  ", style="dim")
        subtitle.append("Phase: ", style="dim")
        subtitle.append(f"{self.metrics['phase']}", style="bold green")

        return Panel(
            Align.center(Group(title, subtitle)),
            box=HEAVY,
            style=Style(color=self.COLORS["primary"], bgcolor=self.COLORS["bg"]),
            padding=(1, 2),
        )

    def render_agents(self) -> Panel:
        """Render animated agent windows."""
        # Create grid for agent positions
        grid = Table.grid(padding=0)
        grid.add_column(justify="left", width=120)

        # Get terminal size for physics
        width = self.console.width
        height = 30

        # Update physics
        dt = 0.1
        for agent in self.agents:
            agent.update_physics(dt, width, height)

        # Render agents as floating windows
        lines = []
        for agent in self.agents:
            icon, color, status_text = agent.status.value

            # Agent window with personality
            window = Text()
            window.append(f"{icon} ", style=f"bold {color}")
            window.append(f"{agent.name}", style=f"bold {self.COLORS['text']}")
            window.append(f" [{agent.score}/100]", style=f"dim {self.COLORS['muted']}")

            if agent.vote is not None:
                vote_icon = "✓" if agent.vote else "✗"
                vote_color = "green" if agent.vote else "red"
                window.append(f"  {vote_icon}", style=f"bold {vote_color}")

            window.append(f"\n   {status_text}", style=f"italic {self.COLORS['muted']}")

            if agent.message:
                window.append(f"\n   {agent.message[:40]}", style=f"dim {self.COLORS['muted']}")

            lines.append(window)

        # Combine into grid
        for line in lines:
            grid.add_row(line)

        return Panel(
            grid,
            title="[bold cyan]Agent Swarm[/bold cyan]",
            border_style=self.COLORS["info"],
            box=ROUNDED,
            padding=(1, 2),
        )

    def render_consensus(self) -> Panel:
        """Render Byzantine consensus visualization."""
        table = Table(show_header=True, box=ROUNDED, padding=(0, 1))
        table.add_column("Phase", style="bold magenta", width=12)
        table.add_column("Votes", style="cyan", width=8)
        table.add_column("Quorum", style="yellow", width=8)
        table.add_column("Status", style="green", width=30)

        # Consensus metrics
        votes_count = len(self.consensus_round.votes)
        quorum = self.consensus_round.quorum
        has_consensus = self.consensus_round.has_consensus()

        # Status with personality
        if has_consensus:
            status = Text("🎉 CONSENSUS REACHED", style="bold green")
        elif votes_count >= quorum - 1:
            status = Text("🔥 Almost there...", style="bold yellow")
        elif votes_count > 0:
            status = Text("🗳️  Voting in progress", style="cyan")
        else:
            status = Text("⏳ Waiting for votes", style="dim")

        table.add_row(
            self.consensus_round.phase,
            f"{votes_count}/7",
            f"{quorum}",
            status,
        )

        # Vote breakdown
        if self.consensus_round.votes:
            approve = sum(1 for v in self.consensus_round.votes if v.vote)
            reject = len(self.consensus_round.votes) - approve

            vote_bar = Text()
            vote_bar.append("✓ " * approve, style="bold green")
            vote_bar.append("✗ " * reject, style="bold red")

            table.add_row("", "", "", vote_bar)

        return Panel(
            table,
            title="[bold magenta]Byzantine Consensus[/bold magenta]",
            border_style=self.COLORS["accent"],
            box=HEAVY,
            padding=(1, 2),
        )

    def render_metrics(self) -> Panel:
        """Render training metrics."""
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Metric", style=f"bold {self.COLORS['muted']}", width=20)
        table.add_column("Value", style=f"bold {self.COLORS['text']}", width=30)

        # Format metrics with personality
        loss_color = (
            "green"
            if self.metrics["loss"] < 1.0
            else "yellow"
            if self.metrics["loss"] < 2.0
            else "red"
        )

        table.add_row(
            "📊 Training Loss",
            Text(f"{self.metrics['loss']:.4f}", style=f"bold {loss_color}"),
        )
        table.add_row(
            "🎯 Current Phase",
            Text(self.metrics["phase"], style="bold cyan"),
        )
        table.add_row(
            "📝 Receipts Processed",
            Text(f"{self.metrics['receipts']:,}", style="bold magenta"),
        )
        table.add_row(
            "✅ Validations",
            Text(f"{self.metrics['validations']}", style="bold green"),
        )

        return Panel(
            table,
            title="[bold yellow]Live Metrics[/bold yellow]",
            border_style=self.COLORS["warning"],
            box=ROUNDED,
            padding=(1, 2),
        )

    def render_activity(self) -> Panel:
        """Render activity log."""
        log_text = Text()

        for entry in reversed(self.activity_log):
            # Color code based on content
            if "ERROR" in entry or "REJECT" in entry:
                style = "red"
            elif "SUCCESS" in entry or "APPROVE" in entry or "CONSENSUS" in entry:
                style = "green"
            elif "WARNING" in entry:
                style = "yellow"
            else:
                style = self.COLORS["muted"]

            log_text.append(f"• {entry}\n", style=style)

        if not self.activity_log:
            log_text.append("Waiting for activity...", style="dim italic")

        return Panel(
            log_text,
            title="[bold cyan]Activity Feed[/bold cyan]",
            border_style=self.COLORS["info"],
            box=ROUNDED,
            padding=(1, 2),
        )

    def render(self) -> Layout:
        """Render complete TUI."""
        layout = Layout()

        # Split into sections
        layout.split_column(
            Layout(name="header", size=7),
            Layout(name="main", ratio=2),
            Layout(name="bottom", ratio=1),
        )

        layout["main"].split_row(
            Layout(name="agents", ratio=2),
            Layout(name="sidebar", ratio=1),
        )

        layout["sidebar"].split_column(
            Layout(name="consensus"),
            Layout(name="metrics"),
        )

        layout["bottom"].split_row(
            Layout(name="activity"),
        )

        # Populate sections
        layout["header"].update(self.render_header())
        layout["agents"].update(self.render_agents())
        layout["consensus"].update(self.render_consensus())
        layout["metrics"].update(self.render_metrics())
        layout["activity"].update(self.render_activity())

        return layout

    async def run(self, refresh_rate: float = 0.1) -> None:
        """Run TUI with live updates."""
        with Live(
            self.render(),
            console=self.console,
            refresh_per_second=10,
            screen=True,
        ) as live:
            try:
                while True:
                    # Update from logs
                    self.update_from_logs()

                    # Update consensus
                    self.update_consensus()

                    # Re-render
                    live.update(self.render())

                    # Sleep
                    await asyncio.sleep(refresh_rate)

            except KeyboardInterrupt:
                self.activity_log.append("🛑 Shutting down gracefully...")
                live.update(self.render())
                await asyncio.sleep(1)


# ═══════════════════════════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════


async def main():
    """Main entry point."""
    import sys

    # Parse log directory
    if len(sys.argv) > 1:
        log_dir = Path(sys.argv[1])
    else:
        # Find most recent log directory
        logs = sorted(Path("logs").glob("parallel_ralph_*"), reverse=True)
        if not logs:
            print("❌ No parallel Ralph logs found. Start training first:")
            print("   ./scripts/launch_parallel_ralph.sh")
            sys.exit(1)
        log_dir = logs[0]

    if not log_dir.exists():
        print(f"❌ Log directory not found: {log_dir}")
        sys.exit(1)

    print("🚀 Starting Parallel Ralph TUI...")
    print(f"📂 Monitoring: {log_dir}")
    print()

    # Run TUI
    tui = ParallelRalphTUI(log_dir)
    await tui.run()


if __name__ == "__main__":
    asyncio.run(main())
