#!/usr/bin/env python3
"""CBF Essentials — Control Barrier Functions Made Simple.

This example demonstrates the fundamentals of Control Barrier Functions (CBF)
in Kagami: the mathematical foundation that ensures h(x) >= 0 ALWAYS.

WHAT YOU'LL LEARN:
==================
1. What is h(x) and why it matters
2. Basic barrier function usage
3. Safety decorators (@cbf_safe, @verify_safety)
4. Audit logging for compliance
5. Registry initialization

Created: December 31, 2025
Colony: Crystal (e₇) — The Judge
"""

from __future__ import annotations

import sys
from pathlib import Path

import torch

# Add paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "packages"))
sys.path.insert(0, str(Path(__file__).parent))

from common.output import (
    print_header,
    print_section,
    print_success,
    print_error,
    print_metrics,
    print_footer,
    print_separator,
)
from common.metrics import Timer, MetricsCollector


# =============================================================================
# SECTION 1: WHAT IS h(x)?
# =============================================================================


def section_1_what_is_h():
    """Explain the fundamental concept of barrier functions."""
    print_section(1, "What is h(x)?")

    print(
        """
   The Control Barrier Function h(x) is a scalar value that tells us:

   • h(x) > 0  → State x is SAFE (green zone)
   • h(x) = 0  → State x is on the BOUNDARY (yellow zone)
   • h(x) < 0  → State x is UNSAFE (red zone, blocked)

   Kagami's invariant: h(x) >= 0 ALWAYS

   Every action passes through CBF before execution.
   If h(x) would go negative, the action is blocked.
"""
    )

    # Demonstrate with simple examples
    print("   Example states:")

    states = [
        ("Door locked, user home", 0.85, "safe"),
        ("Door unlocked, user home", 0.45, "caution"),
        ("Door unlocked, user away", -0.20, "blocked"),
    ]

    for description, h_value, status in states:
        if status == "safe":
            icon = "🟢"
        elif status == "caution":
            icon = "🟡"
        else:
            icon = "🔴"

        print(f"   {icon} h(x) = {h_value:+.2f} | {description}")

    print_success("h(x) is the mathematical guarantee of safety")


# =============================================================================
# SECTION 2: BASIC BARRIER USAGE
# =============================================================================


def section_2_basic_barrier():
    """Demonstrate basic barrier function usage."""
    print_separator()
    print_section(2, "Basic Barrier Function Usage")

    from kagami.core.safety import OptimalCBF, OptimalCBFConfig

    # Create CBF with configuration
    config = OptimalCBFConfig(
        observation_dim=8,
        state_dim=8,
        control_dim=4,
        metric_threshold=0.3,
        use_neural_residual=True,
    )

    cbf = OptimalCBF(config)

    # Sample observation and nominal control
    obs = torch.randn(4, 8)  # Batch of 4 observations
    u_nominal = torch.randn(4, 4)  # Nominal controls

    # Forward pass through CBF
    u_safe, penalty, info = cbf(obs, u_nominal)

    print(f"   Input observation shape: {obs.shape}")
    print(f"   Nominal control shape: {u_nominal.shape}")
    print(f"   Safe control shape: {u_safe.shape}")
    print()
    print(f"   h(x) values: {info['h_metric'].tolist()}")
    print(f"   Min h(x): {info['h_metric'].min().item():.4f}")
    print(f"   Safety penalty: {penalty.item():.4f}")

    # Check safety
    all_safe = (info["h_metric"] >= 0).all().item()
    if all_safe:
        print_success("All states are safe", f"min h(x) = {info['h_metric'].min():.4f}")
    else:
        print_error("Some states are unsafe!")


# =============================================================================
# SECTION 3: SAFETY DECORATORS
# =============================================================================


def section_3_decorators():
    """Demonstrate safety decorators."""
    print_separator()
    print_section(3, "Safety Decorators")

    print(
        """
   Decorators wrap functions with automatic safety checks:

   @enforce_cbf(barrier_name="...", use_registry=True)
      — Enforces h(x) >= 0, blocks on violation

   @monitor_cbf(barrier_name="...", alert_threshold=0.1)
      — Monitors h(x), logs without blocking

   @enforce_tier1("memory")
      — Organism-level enforcement

   @enforce_tier2("colony_budget")
      — Colony-level enforcement

   @enforce_tier3("output_safety")
      — Action-level enforcement
"""
    )

    # Show usage example
    print("   Example usage:")
    print(
        """
      from kagami.core.safety.cbf_decorators import enforce_cbf

      @enforce_cbf(
          cbf_func=lambda state: 0.5 - state.get('memory_pct', 0),
          violation_handler=lambda: gc.collect()
      )
      def allocate_memory(self, size: int):
          self.memory += size
          return self.memory
"""
    )

    # Demonstrate inline barrier check
    print("   Live demonstration (inline barrier check):")

    def check_light_safety(level: int) -> float:
        """h(x) for light level — safe if <= 100."""
        return 1.0 - (level / 100.0) if level <= 100 else -0.5

    test_levels = [50, 80, 100, 150]
    for level in test_levels:
        h_value = check_light_safety(level)
        status = "✓ safe" if h_value >= 0 else "✗ blocked"
        print(f"      Light {level}%: h(x) = {h_value:+.2f} {status}")

    print_success("Decorator patterns demonstrated")


# =============================================================================
# SECTION 4: AUDIT LOGGING
# =============================================================================


def section_4_audit_logging():
    """Demonstrate audit logging for CBF decisions."""
    print_separator()
    print_section(4, "Audit Logging")

    from kagami.core.safety.cbf_utils import create_cbf_monitor

    print(
        """
   Every CBF decision is logged for audit compliance:

   • Timestamp of check
   • h(x) value at decision time
   • Action requested vs action taken
   • Colony that processed the request
   • Correlation ID for tracing
"""
    )

    # Create monitor with logging
    monitor = create_cbf_monitor(
        cbf_threshold=0.0,
        cbf_warn=0.15,
        history_size=100,
    )

    # Simulate several safety checks
    scenarios = [
        ("Lock all doors (goodnight)", torch.tensor([0.9, 0.85, 0.88, 0.92, 0.87, 0.90, 0.86])),
        ("Turn off lights (away)", torch.tensor([0.5, 0.45, 0.52, 0.48, 0.51, 0.49, 0.47])),
        ("Unlock door (user away)", torch.tensor([0.1, 0.05, -0.1, 0.08, 0.12, 0.07, 0.09])),
    ]

    print("   Audit log entries:")
    print()

    for description, h_values in scenarios:
        result = monitor.check(h_values)

        status_icon = {"safe": "✅", "warning": "⚠️", "violation": "❌"}.get(result.status, "❓")

        print(f"   {status_icon} [{result.status.upper():9s}] {description}")
        print(
            f"      h_min={result.details['min_h']:.3f}, unsafe={result.details['unsafe_colonies']}"
        )

    # Generate report
    report = monitor.report()
    print()
    print("   Audit Summary:")
    print(f"      Total checks: {report['total_checks']}")
    print(f"      Violations: {report['violations']} ({report['violation_rate']:.0%})")
    print(f"      Warnings: {report['warnings']} ({report['warning_rate']:.0%})")

    print_success("Audit logging enabled", f"{report['total_checks']} events recorded")


# =============================================================================
# SECTION 5: REGISTRY INITIALIZATION
# =============================================================================


def section_5_registry():
    """Demonstrate CBF registry initialization."""
    print_separator()
    print_section(5, "Registry Initialization")

    from kagami.core.safety import CBFRegistry

    print(
        """
   The CBF Registry manages all safety barriers in the system:

   • Tier 1: Organism-level barriers (global constraints)
   • Tier 2: Colony-level barriers (per-agent limits)
   • Tier 3: Action-level barriers (per-command checks)
"""
    )

    # Get singleton registry
    registry = CBFRegistry()

    # Get stats
    stats = registry.get_stats()

    # Show registered barriers
    print("   Registered barrier types:")

    tier_info = [
        (1, "Tier 1 (Organism)", "System-wide resource limits", stats["tier_1"]),
        (2, "Tier 2 (Colony)", "Per-colony action bounds", stats["tier_2"]),
        (3, "Tier 3 (Action)", "Individual command safety", stats["tier_3"]),
    ]

    for _tier, name, description, count in tier_info:
        print(f"      • {name}: {description} [{count} registered]")

    # Show safety hierarchy
    print()
    print("   Safety Hierarchy:")
    print("      ┌─────────────────────────────────────────┐")
    print("      │  TIER 1: ORGANISM (System-wide)        │")
    print("      │  • Memory/disk limits                   │")
    print("      │  • Process count limits                 │")
    print("      ├─────────────────────────────────────────┤")
    print("      │  TIER 2: COLONY (Per-colony)           │")
    print("      │  • Crystal must verify before complete │")
    print("      │  • Flow can only retry 3 times         │")
    print("      ├─────────────────────────────────────────┤")
    print("      │  TIER 3: ACTION (Per-action)           │")
    print("      │  • Each command checked before exec    │")
    print("      │  • Output content safety               │")
    print("      └─────────────────────────────────────────┘")

    print_success("Registry initialized", "3-tier safety hierarchy active")


# =============================================================================
# MAIN
# =============================================================================


def main():
    """Run CBF Essentials demonstration."""
    print_header("CBF ESSENTIALS", "🛡️")

    metrics = MetricsCollector("cbf_essentials")

    with Timer() as t:
        section_1_what_is_h()
        section_2_basic_barrier()
        section_3_decorators()
        section_4_audit_logging()
        section_5_registry()

    metrics.record_timing("total", t.elapsed)
    metrics.increment("sections", 5)

    print_metrics(
        {
            "Total time": f"{t.elapsed:.2f}s",
            "Sections": 5,
            "Safety invariant": "h(x) >= 0 ALWAYS",
        }
    )

    print_footer(
        message="CBF Essentials complete!",
        next_steps=[
            "Run cbf_advanced_demo.py for spectral barriers, fault tolerance, QP",
            "Run cbf_training.py to train your own barriers",
            "See docs/05_HOW_I_THINK.md for safety architecture",
        ],
    )


if __name__ == "__main__":
    main()
