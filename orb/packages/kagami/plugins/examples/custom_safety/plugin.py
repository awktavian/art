"""Code Security Filter Plugin - Custom safety filter for code operations.

This plugin demonstrates creating a custom safety filter that checks for
security vulnerabilities in code-related operations.

Capabilities:
- Detect dangerous code patterns
- Check for secrets in code
- Validate file operations
- Assess code complexity risk
- Integration with CBF system

Created: December 28, 2025
"""

from __future__ import annotations

import logging
import re
from typing import Any

from kagami.plugins.base import BasePlugin, HealthCheckResult, PluginMetadata
from kagami.plugins.hooks import HookContext, HookType, get_hook_registry

logger = logging.getLogger(__name__)


class CodeSecurityFilter:
    """Custom safety filter for code security checks."""

    # Dangerous patterns to detect
    DANGEROUS_PATTERNS = [
        (r"eval\(", "Code execution via eval()"),
        (r"exec\(", "Code execution via exec()"),
        (r"__import__\(", "Dynamic imports"),
        (r"subprocess\.(call|run|Popen)", "System command execution"),
        (r"os\.system\(", "OS command execution"),
        (r"rm\s+-rf\s+/", "Dangerous file deletion"),
    ]

    # Secret patterns to detect
    SECRET_PATTERNS = [
        (r"password\s*=\s*['\"][^'\"]+['\"]", "Hardcoded password"),
        (r"api[_-]?key\s*=\s*['\"][^'\"]+['\"]", "Hardcoded API key"),
        (r"secret\s*=\s*['\"][^'\"]+['\"]", "Hardcoded secret"),
        (r"token\s*=\s*['\"][^'\"]+['\"]", "Hardcoded token"),
    ]

    def __init__(self):
        """Initialize code security filter."""
        self._checks_performed = 0
        self._threats_detected = 0

    def check_safety(self, content: str, context: dict[str, Any]) -> dict[str, Any]:
        """Check code content for security issues.

        Args:
            content: Code content to check
            context: Operation context

        Returns:
            Safety check result with threat level and details
        """
        self._checks_performed += 1

        threats = []
        threat_level = 0.0

        # Check for dangerous patterns
        for pattern, description in self.DANGEROUS_PATTERNS:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                threats.append(
                    {
                        "type": "dangerous_pattern",
                        "pattern": pattern,
                        "description": description,
                        "matches": len(matches),
                    }
                )
                threat_level += 0.3 * len(matches)

        # Check for secrets
        for pattern, description in self.SECRET_PATTERNS:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                threats.append(
                    {
                        "type": "hardcoded_secret",
                        "pattern": pattern,
                        "description": description,
                        "matches": len(matches),
                    }
                )
                threat_level += 0.4 * len(matches)

        # Check code complexity (lines of code as proxy)
        lines = content.split("\n")
        complexity = len(lines)
        if complexity > 1000:
            threats.append(
                {
                    "type": "high_complexity",
                    "description": "Code exceeds complexity threshold",
                    "lines": complexity,
                }
            )
            threat_level += 0.2

        # Normalize threat level to [0, 1]
        threat_level = min(1.0, threat_level)

        if threats:
            self._threats_detected += len(threats)

        # Compute h(x) value (h >= 0 is safe, h < 0 is unsafe)
        # h(x) = 1.0 - threat_level
        h_x = 1.0 - threat_level

        return {
            "safe": h_x >= 0.0,
            "h_x": h_x,
            "threat_level": threat_level,
            "threats": threats,
            "checks_performed": self._checks_performed,
            "threats_detected": self._threats_detected,
        }

    def get_stats(self) -> dict[str, Any]:
        """Get filter statistics."""
        return {
            "checks_performed": self._checks_performed,
            "threats_detected": self._threats_detected,
        }


class CodeSecurityFilterPlugin(BasePlugin):
    """Plugin that adds code security safety filter."""

    def __init__(self):
        """Initialize plugin."""
        super().__init__()
        self._filter: CodeSecurityFilter | None = None
        self._hook_registry = get_hook_registry()

    @classmethod
    def get_metadata(cls) -> PluginMetadata:
        """Get plugin metadata."""
        return PluginMetadata(
            plugin_id="kagami.code_security_filter",
            name="Code Security Filter",
            version="1.0.0",
            description="Custom safety filter for code security checks",
            author="Kagami Team",
            entry_point="kagami.plugins.examples.custom_safety.plugin:CodeSecurityFilterPlugin",
            dependencies=[],
            capabilities=["safety_filter", "code_security"],
            kagami_version_min="0.1.0",
            kagami_version_max="999.0.0",
            tags=["safety", "security", "code"],
        )

    def on_init(self) -> None:
        """Initialize plugin."""
        logger.info("Initializing Code Security Filter plugin")

        # Create filter
        self._filter = CodeSecurityFilter()

        # Register safety hooks
        self._hook_registry.register_hook(
            HookType.PRE_SAFETY_CHECK,
            self._pre_safety_check,
            plugin_id=self.get_metadata().plugin_id,
        )

        self._hook_registry.register_hook(
            HookType.SAFETY_FILTER,
            self._safety_filter,
            plugin_id=self.get_metadata().plugin_id,
        )

    def on_start(self) -> None:
        """Start plugin."""
        logger.info("Code Security Filter active")

    def on_stop(self) -> None:
        """Stop plugin."""
        logger.info("Code Security Filter paused")

    def on_cleanup(self) -> None:
        """Cleanup plugin resources."""
        logger.info("Cleaning up Code Security Filter plugin")

        # Unregister hooks
        self._hook_registry.unregister_hook(
            HookType.PRE_SAFETY_CHECK,
            self.get_metadata().plugin_id,
        )
        self._hook_registry.unregister_hook(
            HookType.SAFETY_FILTER,
            self.get_metadata().plugin_id,
        )

        self._filter = None

    def health_check(self) -> HealthCheckResult:
        """Check plugin health."""
        if self._filter is None:
            return HealthCheckResult(
                healthy=False,
                status="error",
                details={"error": "Filter not initialized"},
            )

        stats = self._filter.get_stats()
        return HealthCheckResult(
            healthy=True,
            status="ok",
            details={
                "checks_performed": stats["checks_performed"],
                "threats_detected": stats["threats_detected"],
            },
        )

    def _pre_safety_check(self, ctx: HookContext) -> HookContext:
        """Pre-safety check hook.

        Args:
            ctx: Hook context

        Returns:
            Modified context
        """
        # Add custom context for code operations
        operation = ctx.get("operation", "")
        if "code" in operation.lower() or "script" in operation.lower():
            ctx.set("code_operation", True)

        return ctx

    def _safety_filter(self, ctx: HookContext) -> HookContext:
        """Safety filter hook.

        Args:
            ctx: Hook context

        Returns:
            Modified context with safety check results
        """
        if self._filter is None:
            return ctx

        # Only apply to code operations
        if not ctx.get("code_operation", False):
            return ctx

        # Get content to check
        content = ctx.get("user_input", "") or ctx.get("content", "")
        if not content:
            return ctx

        # Run security check
        result = self._filter.check_safety(content, ctx.data)

        # Add results to context
        ctx.set("code_security_check", result)

        # If unsafe, update overall safety assessment
        if not result["safe"]:
            logger.warning(
                f"Code security threats detected: {len(result['threats'])} "
                f"(h(x)={result['h_x']:.3f})"
            )

            # Merge with existing h_x if present
            existing_h_x = ctx.get("h_x")
            if existing_h_x is not None:
                # Use minimum h(x) (most conservative)
                ctx.set("h_x", min(existing_h_x, result["h_x"]))
            else:
                ctx.set("h_x", result["h_x"])

            # Add threat details
            existing_threats = ctx.get("threats", [])
            existing_threats.extend(result["threats"])
            ctx.set("threats", existing_threats)

        return ctx

    def get_filter(self) -> CodeSecurityFilter | None:
        """Get the security filter.

        Returns:
            Code security filter instance
        """
        return self._filter


__all__ = ["CodeSecurityFilter", "CodeSecurityFilterPlugin"]
