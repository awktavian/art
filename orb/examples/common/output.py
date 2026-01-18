"""Rich terminal output utilities for Kagami examples.

Provides consistent, beautiful terminal output across all examples.
"""

from __future__ import annotations

import sys
from typing import Any


# ANSI color codes
class Colors:
    """ANSI color codes for terminal output."""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # Standard colors
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"

    # Kagami brand colors
    GOLD = "\033[38;5;220m"
    VOID = "\033[38;5;232m"


def supports_color() -> bool:
    """Check if terminal supports color output."""
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def _c(text: str, color: str) -> str:
    """Apply color to text if terminal supports it."""
    if supports_color():
        return f"{color}{text}{Colors.RESET}"
    return text


def print_header(title: str, emoji: str = "🔷") -> None:
    """Print a formatted header for an example.

    Args:
        title: The title to display
        emoji: Emoji prefix for the title
    """
    width = 64
    line = "═" * width
    print()
    print(_c(line, Colors.GOLD))
    print(_c(f"  {emoji} {title.upper()}", Colors.BOLD))
    print(_c(line, Colors.GOLD))
    print()


def print_section(number: int, title: str) -> None:
    """Print a numbered section header.

    Args:
        number: Section number
        title: Section title
    """
    print(f"{_c(str(number) + '.', Colors.CYAN)} {_c(title, Colors.BOLD)}...")


def print_success(message: str, detail: str | None = None) -> None:
    """Print a success message with checkmark.

    Args:
        message: Success message
        detail: Optional detail in parentheses
    """
    check = _c("✓", Colors.GREEN)
    msg = f"   {check} {message}"
    if detail:
        msg += f" {_c(f'({detail})', Colors.DIM)}"
    print(msg)


def print_error(message: str, detail: str | None = None) -> None:
    """Print an error message with X.

    Args:
        message: Error message
        detail: Optional detail in parentheses
    """
    x = _c("✗", Colors.RED)
    msg = f"   {x} {message}"
    if detail:
        msg += f" {_c(f'({detail})', Colors.DIM)}"
    print(msg)


def print_warning(message: str, detail: str | None = None) -> None:
    """Print a warning message.

    Args:
        message: Warning message
        detail: Optional detail in parentheses
    """
    warn = _c("⚠", Colors.YELLOW)
    msg = f"   {warn} {message}"
    if detail:
        msg += f" {_c(f'({detail})', Colors.DIM)}"
    print(msg)


def print_info(message: str) -> None:
    """Print an info message.

    Args:
        message: Info message
    """
    print(f"   {_c('ℹ', Colors.BLUE)} {message}")


def print_metrics(metrics: dict[str, Any]) -> None:
    """Print metrics in a formatted block.

    Args:
        metrics: Dictionary of metric name -> value pairs
    """
    print()
    print(f"{_c('📊 Metrics:', Colors.CYAN)}")
    for name, value in metrics.items():
        if isinstance(value, float):
            formatted = f"{value:.2f}"
        elif isinstance(value, int):
            formatted = f"{value:,}"
        else:
            formatted = str(value)
        print(f"   {name}: {_c(formatted, Colors.BOLD)}")


def print_separator() -> None:
    """Print a horizontal separator line."""
    print()
    print(_c("─" * 64, Colors.DIM))
    print()


def print_footer(
    message: str = "Demo complete!",
    next_steps: list[str] | None = None,
    success: bool = True,
) -> None:
    """Print a formatted footer for an example.

    Args:
        message: Completion message
        next_steps: Optional list of next steps to try
        success: Whether the demo was successful
    """
    width = 64
    line = "═" * width

    print()
    print(_c(line, Colors.GOLD))

    icon = _c("✓", Colors.GREEN) if success else _c("✗", Colors.RED)
    print(f"  {icon} {message}")

    if next_steps:
        print()
        print(f"  {_c('Next steps:', Colors.DIM)}")
        for step in next_steps:
            print(f"    → {step}")

    print(_c(line, Colors.GOLD))
    print()


def print_colony(
    colony_name: str,
    message: str,
    activation: float | None = None,
) -> None:
    """Print a colony-specific message with appropriate color.

    Args:
        colony_name: Name of the colony (spark, forge, flow, etc.)
        message: Message to display
        activation: Optional activation level (0-1)
    """
    colony_colors = {
        "spark": Colors.MAGENTA,
        "forge": Colors.RED,
        "flow": Colors.CYAN,
        "nexus": Colors.YELLOW,
        "beacon": Colors.GREEN,
        "grove": Colors.MAGENTA,
        "crystal": Colors.BLUE,
    }
    colony_emoji = {
        "spark": "🔥",
        "forge": "⚒️",
        "flow": "🌊",
        "nexus": "🔗",
        "beacon": "🗼",
        "grove": "🌿",
        "crystal": "💎",
    }

    color = colony_colors.get(colony_name.lower(), Colors.WHITE)
    emoji = colony_emoji.get(colony_name.lower(), "●")

    name_formatted = _c(f"{emoji} {colony_name.upper()}", color)
    activation_str = ""
    if activation is not None:
        bar_width = 10
        filled = int(activation * bar_width)
        bar = "█" * filled + "░" * (bar_width - filled)
        activation_str = f" [{bar}] {activation:.0%}"

    print(f"   {name_formatted}: {message}{activation_str}")


def print_table(
    headers: list[str],
    rows: list[list[Any]],
    title: str | None = None,
) -> None:
    """Print a formatted table.

    Args:
        headers: Column headers
        rows: List of row data
        title: Optional table title
    """
    if title:
        print(f"\n{_c(title, Colors.BOLD)}")

    # Calculate column widths
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))

    # Print header
    header_line = " │ ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    print(f"   {_c(header_line, Colors.BOLD)}")
    print(f"   {'─┼─'.join('─' * w for w in widths)}")

    # Print rows
    for row in rows:
        row_line = " │ ".join(str(cell).ljust(widths[i]) for i, cell in enumerate(row))
        print(f"   {row_line}")
