# pyright: reportGeneralTypeIssues=false
"""Unified Action Executor — Routes ALL actions to execution.

This is THE execution bridge that connects:
    MotorDecoder outputs → Actual execution (Composio, SmartHome, Meta, Builtin)

ARCHITECTURE (Dec 30, 2025):
============================
MotorDecoder produces logits for:
    - digital_tools [50]: Composio WRITE actions (send_email, create_task, etc.)
    - smarthome_actions [50]: SmartHome SET actions (set_lights, announce, etc.)
    - meta_actions [7]: Control flow (observe, wait, delegate, etc.)

Additionally, this executor handles:
    - builtin_tools [43]: General purpose tools (web_search, python_execute, etc.)

TOTAL ACTION SPACE: ~680 actions across 4 domains

This executor:
1. Decodes best action from each head
2. Routes to appropriate executor based on action type
3. Falls back to LLM reasoning when confidence < threshold
4. Ensures ALL paths are equally wired and functional

The Markov blanket effector boundary (a → η) is enforced here.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import torch

if TYPE_CHECKING:
    from kagami_smarthome import SmartHomeController

    from kagami.core.embodiment.motor_decoder import MotorDecoder
    from kagami.core.services.composio import ComposioIntegrationService

logger = logging.getLogger(__name__)


@dataclass
class ActionResult:
    """Result of executing an action."""

    success: bool
    action_type: str  # "digital", "smarthome", "meta"
    action_name: str
    confidence: float
    result: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    method: str = "motor_decoder"  # "motor_decoder", "llm_fallback"


@dataclass
class ExecutionContext:
    """Context for action execution."""

    goal: str | None = None
    room: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    confidence_threshold: float = 0.3
    allow_llm_fallback: bool = True


class UnifiedActionExecutor:
    """Routes ALL actions to actual execution.

    EQUAL PATH WIRING (4 domains):
    ==============================
    1. digital_tools → Composio.execute_action()
    2. smarthome_actions → SmartHomeController.<method>()
    3. meta_actions → Internal handlers (observe, wait, delegate)
    4. builtin_tools → kagami.tools.TOOL_REGISTRY.<function>()

    LLM FALLBACK:
    =============
    When confidence < threshold, uses IntelligentActionMapper
    to reason about the best action from the goal context.

    TOTAL ACTION SPACE: ~680 actions
    """

    def __init__(self) -> None:
        self._motor_decoder: MotorDecoder | None = None
        self._composio: ComposioIntegrationService | None = None
        self._controller: SmartHomeController | None = None
        self._action_mapper: Any = None  # IntelligentActionMapper
        self._tools_integration: Any = None  # ChronosToolsIntegration
        self._initialized = False

        # Tracking
        self._total_executions = 0
        self._digital_executions = 0
        self._smarthome_executions = 0
        self._meta_executions = 0
        self._builtin_executions = 0
        self._llm_fallbacks = 0

    async def initialize(self) -> bool:
        """Initialize all execution backends."""
        if self._initialized:
            return True

        try:
            # Motor decoder
            from kagami.core.embodiment.motor_decoder import get_motor_decoder

            self._motor_decoder = get_motor_decoder()

            # Composio for digital actions
            try:
                from kagami.core.services.composio import get_composio_service

                self._composio = get_composio_service()
                if not self._composio.initialized:
                    await self._composio.initialize()
            except Exception as e:
                logger.warning(f"Composio unavailable: {e}")
                self._composio = None

            # SmartHome for physical actions
            try:
                import sys

                sys.path.insert(0, "packages")
                from kagami_smarthome import get_smart_home

                self._controller = await get_smart_home()
            except Exception as e:
                logger.warning(f"SmartHome unavailable: {e}")
                self._controller = None

            # Action mapper for LLM fallback
            try:
                from kagami.core.motivation.intelligent_action_mapper import (
                    get_intelligent_action_mapper,
                )

                self._action_mapper = get_intelligent_action_mapper()
            except Exception as e:
                logger.warning(f"ActionMapper unavailable: {e}")
                self._action_mapper = None

            # Tools integration for builtin tools
            try:
                from kagami.core.tools_integration import get_kagami_tools_integration

                self._tools_integration = get_kagami_tools_integration()
                await self._tools_integration.initialize()
            except Exception as e:
                logger.warning(f"ToolsIntegration unavailable: {e}")
                self._tools_integration = None

            self._initialized = True
            logger.info(
                f"✅ UnifiedActionExecutor: composio={self._composio is not None}, "
                f"smarthome={self._controller is not None}, "
                f"llm_fallback={self._action_mapper is not None}, "
                f"builtin_tools={self._tools_integration is not None}"
            )
            return True

        except Exception as e:
            logger.error(f"UnifiedActionExecutor initialization failed: {e}")
            return False

    async def execute_from_decoder(
        self,
        outputs: dict[str, torch.Tensor],
        context: ExecutionContext | None = None,
    ) -> ActionResult:
        """Execute best action from MotorDecoder outputs.

        Args:
            outputs: Dict from MotorDecoder.forward() containing:
                - digital_tools: [B, num_digital] logits
                - smarthome_actions: [B, num_smarthome] logits
                - meta_actions: [B, num_meta] logits
                - action_uncertainty: [B, 1] confidence
            context: Optional execution context

        Returns:
            ActionResult with execution status
        """
        if not self._initialized:
            await self.initialize()

        ctx = context or ExecutionContext()
        self._total_executions += 1

        # Get best action across all heads
        best = self._motor_decoder.get_best_action_across_heads(outputs)

        # Check if confidence is below threshold → LLM fallback
        if best["confidence"] < ctx.confidence_threshold and ctx.allow_llm_fallback:
            return await self._execute_llm_fallback(ctx)

        # Route to appropriate executor
        if best["head"] == "digital":
            return await self._execute_digital(best["action"], ctx)
        elif best["head"] == "smarthome":
            return await self._execute_smarthome(best["action"], ctx)
        elif best["head"] == "meta":
            return await self._execute_meta(best["action"], ctx)
        else:
            return ActionResult(
                success=False,
                action_type="unknown",
                action_name=best.get("action", "unknown"),
                confidence=best.get("confidence", 0.0),
                error=f"Unknown action head: {best.get('head')}",
            )

    async def _execute_digital(self, action_name: str, ctx: ExecutionContext) -> ActionResult:
        """Execute a Composio digital action."""
        self._digital_executions += 1

        if not self._composio or not self._composio.initialized:
            return ActionResult(
                success=False,
                action_type="digital",
                action_name=action_name,
                confidence=0.0,
                error="Composio not available",
            )

        try:
            result = await self._composio.execute_action(action_name, ctx.parameters)

            success = result.get("success", False)
            return ActionResult(
                success=success,
                action_type="digital",
                action_name=action_name,
                confidence=1.0 if success else 0.0,
                result=result,
            )

        except Exception as e:
            logger.error(f"Digital action execution failed: {e}")
            return ActionResult(
                success=False,
                action_type="digital",
                action_name=action_name,
                confidence=0.0,
                error=str(e),
            )

    async def _execute_smarthome(self, action_name: str, ctx: ExecutionContext) -> ActionResult:
        """Execute a SmartHome physical action."""
        self._smarthome_executions += 1

        if not self._controller:
            return ActionResult(
                success=False,
                action_type="smarthome",
                action_name=action_name,
                confidence=0.0,
                error="SmartHome controller not available",
            )

        try:
            # Map action name to controller method
            method = getattr(self._controller, action_name, None)
            if method is None:
                return ActionResult(
                    success=False,
                    action_type="smarthome",
                    action_name=action_name,
                    confidence=0.0,
                    error=f"Unknown SmartHome action: {action_name}",
                )

            # Execute with context parameters
            if ctx.room:
                result = await method(rooms=[ctx.room], **ctx.parameters)
            else:
                result = await method(**ctx.parameters)

            return ActionResult(
                success=bool(result),
                action_type="smarthome",
                action_name=action_name,
                confidence=1.0,
                result={"executed": action_name, "room": ctx.room},
            )

        except Exception as e:
            logger.error(f"SmartHome action execution failed: {e}")
            return ActionResult(
                success=False,
                action_type="smarthome",
                action_name=action_name,
                confidence=0.0,
                error=str(e),
            )

    async def _execute_desktop(self, action_name: str, ctx: ExecutionContext) -> ActionResult:
        """Execute a desktop/VM control action via HAL VM adapters.

        Routes to:
        - Tier 1: Peekaboo (host macOS)
        - Tier 2: CUA/Lume (sandboxed macOS VMs)
        - Tier 3: Parallels (Windows/Linux VMs)
        """
        try:
            # Lazy import to avoid circular dependency
            from kagami_hal.adapters.vm import (
                ParallelsAdapter,
                PeekabooAdapter,
            )

            # Determine which adapter to use based on context
            vm_name = ctx.parameters.get("vm_name")
            tier = ctx.parameters.get("tier", 1)

            if tier == 3 or vm_name:
                # Tier 3: Parallels VM
                adapter = ParallelsAdapter(vm_name or "Gaming")
            else:
                # Tier 1: Host macOS via Peekaboo
                adapter = PeekabooAdapter()

            await adapter.initialize()

            # Map action names to adapter methods
            action_map = {
                # Sensors
                "desktop_screenshot": lambda: adapter.screenshot(),
                "desktop_screenshot_window": lambda: adapter.screenshot(
                    window=ctx.parameters.get("window")
                ),
                "desktop_accessibility_tree": lambda: adapter.get_accessibility_tree(
                    ctx.parameters.get("app")
                ),
                "desktop_find_element": lambda: adapter.find_element(ctx.parameters.get("label")),
                "desktop_list_apps": lambda: adapter.list_running_apps(),
                "desktop_get_frontmost": lambda: adapter.get_frontmost_app(),
                "desktop_get_clipboard": lambda: adapter.get_clipboard(),
                "vm_get_status": lambda: adapter.get_status(),
                # Mouse effectors
                "desktop_click": lambda: adapter.click(
                    ctx.parameters.get("x", 0),
                    ctx.parameters.get("y", 0),
                    ctx.parameters.get("button", "left"),
                ),
                "desktop_double_click": lambda: adapter.double_click(
                    ctx.parameters.get("x", 0),
                    ctx.parameters.get("y", 0),
                ),
                "desktop_right_click": lambda: adapter.click(
                    ctx.parameters.get("x", 0),
                    ctx.parameters.get("y", 0),
                    button="right",
                ),
                "desktop_drag": lambda: adapter.drag(
                    ctx.parameters.get("from_x", 0),
                    ctx.parameters.get("from_y", 0),
                    ctx.parameters.get("to_x", 0),
                    ctx.parameters.get("to_y", 0),
                ),
                "desktop_scroll": lambda: adapter.scroll(
                    ctx.parameters.get("direction", "down"),
                    ctx.parameters.get("amount", 3),
                ),
                "desktop_move": lambda: adapter.move(
                    ctx.parameters.get("x", 0),
                    ctx.parameters.get("y", 0),
                ),
                # Keyboard effectors
                "desktop_type": lambda: adapter.type_text(ctx.parameters.get("text", "")),
                "desktop_hotkey": lambda: adapter.hotkey(*ctx.parameters.get("keys", [])),
                "desktop_press": lambda: adapter.press(ctx.parameters.get("key", "")),
                "desktop_paste": lambda: adapter.paste(ctx.parameters.get("text")),
                # App control
                "desktop_launch_app": lambda: adapter.launch_app(ctx.parameters.get("app", "")),
                "desktop_quit_app": lambda: adapter.quit_app(ctx.parameters.get("app", "")),
                "desktop_focus_app": lambda: adapter.focus_app(ctx.parameters.get("app", "")),
                # Clipboard
                "desktop_set_clipboard": lambda: adapter.set_clipboard(
                    ctx.parameters.get("text", "")
                ),
                # VM lifecycle
                "vm_start": lambda: adapter.start(),
                "vm_stop": lambda: adapter.stop(),
                "vm_suspend": lambda: adapter.suspend() if hasattr(adapter, "suspend") else None,
                "vm_create_snapshot": lambda: adapter.create_snapshot(
                    ctx.parameters.get("name", "snapshot")
                ),
                "vm_restore_snapshot": lambda: adapter.restore_snapshot(
                    ctx.parameters.get("name", "snapshot")
                ),
                "vm_execute_command": lambda: adapter.execute_command(
                    ctx.parameters.get("command", "")
                ),
            }

            handler = action_map.get(action_name)

            # If not a desktop/VM action, check if it's a CLI action
            if handler is None and action_name.startswith("cli_"):
                return await self._execute_cli(action_name, ctx)

            if handler is None:
                return ActionResult(
                    success=False,
                    action_type="desktop",
                    action_name=action_name,
                    confidence=0.0,
                    error=f"Unknown desktop action: {action_name}",
                )

            result = await handler()

            return ActionResult(
                success=True,
                action_type="desktop",
                action_name=action_name,
                confidence=1.0,
                result=result,
            )

        except ImportError as e:
            logger.warning(f"HAL VM adapters not available: {e}")
            return ActionResult(
                success=False,
                action_type="desktop",
                action_name=action_name,
                confidence=0.0,
                error=f"HAL VM adapters not available: {e}",
            )
        except Exception as e:
            logger.error(f"Desktop action execution failed: {e}")
            return ActionResult(
                success=False,
                action_type="desktop",
                action_name=action_name,
                confidence=0.0,
                error=str(e),
            )

    async def _execute_cli(self, action_name: str, ctx: ExecutionContext) -> ActionResult:
        """Execute a CLI action via the unified CLI adapter.

        Supports:
        - Local execution (macOS, Linux, Windows)
        - Remote execution (Parallels, Lume, SSH)
        """
        try:
            # Lazy import to avoid circular dependency
            from kagami_hal.adapters.cli import ShellType, get_unified_cli

            cli = get_unified_cli()

            # Determine target from context
            target = ctx.parameters.get("target", "local")
            vm_name = ctx.parameters.get("vm_name")
            host = ctx.parameters.get("host")
            user = ctx.parameters.get("user")
            shell_str = ctx.parameters.get("shell", "auto")
            shell = ShellType(shell_str.lower()) if shell_str != "auto" else ShellType.AUTO

            # Map action names to CLI methods
            if action_name == "cli_execute":
                command = ctx.parameters.get("command", "")
                result = await cli.execute(
                    command,
                    target=target,
                    vm_name=vm_name,
                    host=host,
                    user=user,
                    shell=shell,
                    cwd=ctx.parameters.get("cwd"),
                    env=ctx.parameters.get("env"),
                    timeout=ctx.parameters.get("timeout", 30.0),
                )
                return ActionResult(
                    success=result.success,
                    action_type="cli",
                    action_name=action_name,
                    confidence=1.0,
                    result={
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                        "exit_code": result.exit_code,
                        "duration_ms": result.duration_ms,
                    },
                    error=result.stderr if not result.success else None,
                )

            elif action_name == "cli_execute_script":
                script = ctx.parameters.get("script", "")
                result = await cli.execute_script(
                    script,
                    target=target,
                    vm_name=vm_name,
                    host=host,
                    user=user,
                    shell=shell,
                    cwd=ctx.parameters.get("cwd"),
                    env=ctx.parameters.get("env"),
                    timeout=ctx.parameters.get("timeout", 60.0),
                )
                return ActionResult(
                    success=result.success,
                    action_type="cli",
                    action_name=action_name,
                    confidence=1.0,
                    result={
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                        "exit_code": result.exit_code,
                    },
                    error=result.stderr if not result.success else None,
                )

            elif action_name == "cli_which":
                program = ctx.parameters.get("program", "")
                path = await cli.which(
                    program, target=target, vm_name=vm_name, host=host, user=user
                )
                return ActionResult(
                    success=path is not None,
                    action_type="cli",
                    action_name=action_name,
                    confidence=1.0,
                    result={"path": path},
                )

            elif action_name == "cli_get_env":
                name = ctx.parameters.get("name", "")
                value = await cli.local.get_env(name) if target == "local" else None
                return ActionResult(
                    success=value is not None,
                    action_type="cli",
                    action_name=action_name,
                    confidence=1.0,
                    result={"value": value},
                )

            elif action_name == "cli_set_env":
                name = ctx.parameters.get("name", "")
                value = ctx.parameters.get("value", "")
                await cli.local.set_env(name, value)
                return ActionResult(
                    success=True,
                    action_type="cli",
                    action_name=action_name,
                    confidence=1.0,
                    result={"name": name, "value": value},
                )

            elif action_name == "cli_get_cwd":
                cwd = await cli.local.get_cwd()
                return ActionResult(
                    success=True,
                    action_type="cli",
                    action_name=action_name,
                    confidence=1.0,
                    result={"cwd": cwd},
                )

            elif action_name == "cli_set_cwd":
                path = ctx.parameters.get("path", "")
                await cli.local.set_cwd(path)
                return ActionResult(
                    success=True,
                    action_type="cli",
                    action_name=action_name,
                    confidence=1.0,
                    result={"cwd": path},
                )

            elif action_name == "cli_read_file":
                path = ctx.parameters.get("path", "")
                content = await cli.read_file(
                    path, target=target, vm_name=vm_name, host=host, user=user
                )
                return ActionResult(
                    success=True,
                    action_type="cli",
                    action_name=action_name,
                    confidence=1.0,
                    result={"content": content},
                )

            elif action_name == "cli_write_file":
                path = ctx.parameters.get("path", "")
                content = ctx.parameters.get("content", "")
                success = await cli.write_file(
                    path, content, target=target, vm_name=vm_name, host=host, user=user
                )
                return ActionResult(
                    success=success,
                    action_type="cli",
                    action_name=action_name,
                    confidence=1.0,
                    result={"path": path, "written": success},
                )

            elif action_name == "cli_list_files":
                path = ctx.parameters.get("path", ".")
                files = await cli.list_files(
                    path, target=target, vm_name=vm_name, host=host, user=user
                )
                return ActionResult(
                    success=True,
                    action_type="cli",
                    action_name=action_name,
                    confidence=1.0,
                    result={"files": files},
                )

            elif action_name == "cli_install_package":
                package = ctx.parameters.get("package", "")
                result = await cli.local.install_package(package)
                return ActionResult(
                    success=result.success,
                    action_type="cli",
                    action_name=action_name,
                    confidence=1.0,
                    result={"stdout": result.stdout, "stderr": result.stderr},
                    error=result.stderr if not result.success else None,
                )

            elif action_name == "cli_run_python":
                code = ctx.parameters.get("code", "")
                result = await cli.local.run_python(code)
                return ActionResult(
                    success=result.success,
                    action_type="cli",
                    action_name=action_name,
                    confidence=1.0,
                    result={"stdout": result.stdout, "stderr": result.stderr},
                    error=result.stderr if not result.success else None,
                )

            elif action_name == "cli_run_remote":
                command = ctx.parameters.get("command", "")
                if target == "parallels":
                    output = await cli.parallels_run(command, vm_name=vm_name)
                elif target == "lume":
                    output = await cli.lume_run(command, vm_name=vm_name)
                elif target == "ssh":
                    output = await cli.ssh_run(command, host=host, user=user or "root")
                else:
                    output = await cli.local_run(command)
                return ActionResult(
                    success=True,
                    action_type="cli",
                    action_name=action_name,
                    confidence=1.0,
                    result={"output": output},
                )

            else:
                return ActionResult(
                    success=False,
                    action_type="cli",
                    action_name=action_name,
                    confidence=0.0,
                    error=f"Unknown CLI action: {action_name}",
                )

        except ImportError as e:
            logger.warning(f"HAL CLI adapters not available: {e}")
            return ActionResult(
                success=False,
                action_type="cli",
                action_name=action_name,
                confidence=0.0,
                error=f"HAL CLI adapters not available: {e}",
            )
        except Exception as e:
            logger.error(f"CLI action execution failed: {e}")
            return ActionResult(
                success=False,
                action_type="cli",
                action_name=action_name,
                confidence=0.0,
                error=str(e),
            )

    async def _execute_meta(self, action_name: str, ctx: ExecutionContext) -> ActionResult:
        """Execute a meta control flow action."""
        self._meta_executions += 1

        meta_handlers = {
            "OBSERVE": self._meta_observe,
            "WAIT": self._meta_wait,
            "DELEGATE": self._meta_delegate,
            "THINK": self._meta_think,
            "PLAN": self._meta_plan,
            "SPEAK": self._meta_speak,
            "LISTEN": self._meta_listen,
        }

        handler = meta_handlers.get(action_name)
        if handler is None:
            return ActionResult(
                success=False,
                action_type="meta",
                action_name=action_name,
                confidence=0.0,
                error=f"Unknown meta action: {action_name}",
            )

        try:
            result = await handler(ctx)
            return ActionResult(
                success=True,
                action_type="meta",
                action_name=action_name,
                confidence=1.0,
                result=result,
            )
        except Exception as e:
            logger.error(f"Meta action execution failed: {e}")
            return ActionResult(
                success=False,
                action_type="meta",
                action_name=action_name,
                confidence=0.0,
                error=str(e),
            )

    async def _meta_observe(self, ctx: ExecutionContext) -> dict[str, Any]:
        """OBSERVE: Gather information without action."""
        logger.info("META: OBSERVE — gathering information")
        return {"action": "observe", "status": "observing"}

    async def _meta_wait(self, ctx: ExecutionContext) -> dict[str, Any]:
        """WAIT: Pause execution."""
        import asyncio

        wait_time = ctx.parameters.get("duration", 1.0)
        logger.info(f"META: WAIT — pausing for {wait_time}s")
        await asyncio.sleep(wait_time)
        return {"action": "wait", "duration": wait_time}

    async def _meta_delegate(self, ctx: ExecutionContext) -> dict[str, Any]:
        """DELEGATE: Pass to another colony."""
        target = ctx.parameters.get("target_colony", "grove")
        logger.info(f"META: DELEGATE — routing to {target}")
        return {"action": "delegate", "target": target}

    async def _meta_think(self, ctx: ExecutionContext) -> dict[str, Any]:
        """THINK: Internal reasoning."""
        logger.info("META: THINK — internal reasoning")
        return {"action": "think", "status": "reasoning"}

    async def _meta_plan(self, ctx: ExecutionContext) -> dict[str, Any]:
        """PLAN: Generate plan."""
        logger.info("META: PLAN — generating plan")
        return {"action": "plan", "status": "planning"}

    async def _meta_speak(self, ctx: ExecutionContext) -> dict[str, Any]:
        """SPEAK: TTS output."""
        text = ctx.parameters.get("text", "")
        if text and self._controller:
            room = ctx.room or "Living Room"
            await self._controller.announce(text, rooms=[room])
        return {"action": "speak", "text": text}

    async def _meta_listen(self, ctx: ExecutionContext) -> dict[str, Any]:
        """LISTEN: STT input."""
        logger.info("META: LISTEN — waiting for input")
        return {"action": "listen", "status": "listening"}

    async def execute_builtin(self, action_name: str, ctx: ExecutionContext) -> ActionResult:
        """Execute a builtin tool from kagami.tools.

        This handles general-purpose tools like:
        - web_search, web_fetch
        - python_execute, shell_execute
        - read_file, write_file
        - analyze_code, generate_code
        - etc.
        """
        self._builtin_executions += 1

        # Try tools integration first
        if self._tools_integration:
            try:
                result = await self._tools_integration.execute_tool(action_name, ctx.parameters)

                return ActionResult(
                    success=result.get("success", False),
                    action_type="builtin",
                    action_name=action_name,
                    confidence=1.0 if result.get("success") else 0.0,
                    result=result,
                )
            except Exception as e:
                logger.debug(f"ToolsIntegration failed: {e}")

        # Fallback to direct tool registry
        try:
            from kagami.tools import get_tool

            tool_fn = get_tool(action_name)
            if tool_fn is None:
                return ActionResult(
                    success=False,
                    action_type="builtin",
                    action_name=action_name,
                    confidence=0.0,
                    error=f"Unknown builtin tool: {action_name}",
                )

            # Execute the tool
            import asyncio
            import inspect

            if inspect.iscoroutinefunction(tool_fn):
                result = await tool_fn(**ctx.parameters)
            else:
                result = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: tool_fn(**ctx.parameters)
                )

            success = isinstance(result, dict) and result.get("success", True)

            return ActionResult(
                success=success,
                action_type="builtin",
                action_name=action_name,
                confidence=1.0,
                result=result if isinstance(result, dict) else {"output": result},
            )

        except Exception as e:
            logger.error(f"Builtin tool execution failed: {e}")
            return ActionResult(
                success=False,
                action_type="builtin",
                action_name=action_name,
                confidence=0.0,
                error=str(e),
            )

    async def execute_by_name(
        self, action_name: str, ctx: ExecutionContext | None = None
    ) -> ActionResult:
        """Execute an action by name (auto-routes to correct executor).

        This is the primary interface for executing actions by name
        without going through the motor decoder.

        MARKOV BLANKET ROUTING:
        =======================
        SENSORS (η → s) are READ-only queries:
            - COMPOSIO_SENSORS: Fetch emails, list files, get calendar
            - SMARTHOME_SENSORS: Get lights, check locks, query presence
            - BUILTIN_SENSORS: Analyze code, search files, web search

        EFFECTORS (a → η) are WRITE operations:
            - COMPOSIO_EFFECTORS: Send emails, create tasks, post messages
            - SMARTHOME_EFFECTORS: Turn on lights, announce, lock doors
            - BUILTIN_EFFECTORS: Execute code, generate content, build
            - META_ACTIONS: Control flow (observe, wait, delegate)

        Args:
            action_name: The action to execute
            ctx: Optional execution context

        Returns:
            ActionResult with execution status
        """
        if not self._initialized:
            await self.initialize()

        ctx = ctx or ExecutionContext()
        self._total_executions += 1

        # Import action lists (Markov blanket categorized)
        from kagami.core.embodiment.action_space import (
            BUILTIN_EFFECTORS,
            BUILTIN_SENSORS,
            COMPOSIO_EFFECTORS,
            COMPOSIO_SENSORS,
            DESKTOP_EFFECTORS,
            DESKTOP_SENSORS,
            META_ACTIONS,
            SMARTHOME_EFFECTORS,
            SMARTHOME_SENSORS,
        )

        # Route based on Markov blanket classification
        # ==== DIGITAL (Composio) ====
        if action_name in COMPOSIO_SENSORS or action_name in COMPOSIO_EFFECTORS:
            return await self._execute_digital(action_name, ctx)

        # ==== PHYSICAL (SmartHome) ====
        elif action_name in SMARTHOME_SENSORS or action_name in SMARTHOME_EFFECTORS:
            return await self._execute_smarthome(action_name, ctx)

        # ==== DESKTOP/VM (Computer Control) ====
        elif action_name in DESKTOP_SENSORS or action_name in DESKTOP_EFFECTORS:
            return await self._execute_desktop(action_name, ctx)

        # ==== META (Control Flow) ====
        elif action_name in META_ACTIONS:
            return await self._execute_meta(action_name, ctx)

        # ==== BUILTIN (General Tools) ====
        elif action_name in BUILTIN_SENSORS or action_name in BUILTIN_EFFECTORS:
            return await self.execute_builtin(action_name, ctx)

        # ==== FALLBACK: Heuristic routing by prefix ====
        elif action_name.startswith(
            ("GMAIL_", "SLACK_", "TWITTER_", "GOOGLE", "LINEAR_", "DISCORD_", "NOTION_", "TODOIST_")
        ):
            return await self._execute_digital(action_name, ctx)
        elif action_name in ["set_lights", "announce", "goodnight", "movie_mode", "lock_all"]:
            return await self._execute_smarthome(action_name, ctx)
        elif action_name in [
            "web_search",
            "python_execute",
            "shell_execute",
            "read_file",
            "analyze_code",
        ]:
            return await self.execute_builtin(action_name, ctx)

        # ==== UNKNOWN: LLM Fallback ====
        else:
            if ctx.allow_llm_fallback:
                ctx.goal = f"Execute action: {action_name}"
                return await self._execute_llm_fallback(ctx)

            return ActionResult(
                success=False,
                action_type="unknown",
                action_name=action_name,
                confidence=0.0,
                error=f"Unknown action: {action_name}",
            )

    async def _execute_llm_fallback(self, ctx: ExecutionContext) -> ActionResult:
        """REMOVED: LLM fallback is now the PRIMARY path, not a fallback.

        All action execution should go through the primary LLM-driven motor decoder.
        This method now raises an error to prevent heuristic fallback usage.

        Raises:
            RuntimeError: Always - this fallback path should not be used
        """
        self._llm_fallbacks += 1

        logger.error(
            "❌ HEURISTIC FALLBACK INVOKED: _execute_llm_fallback should not be called. "
            "All actions must go through primary LLM-driven motor decoder."
        )

        return ActionResult(
            success=False,
            action_type="error",
            action_name="heuristic_fallback_blocked",
            confidence=0.0,
            error="Heuristic fallback blocked - use primary LLM-driven path",
            method="blocked_fallback",
        )

    async def _execute_smarthome_semantic(
        self, category: str, action: str, ctx: ExecutionContext
    ) -> ActionResult:
        """Execute SmartHome action from semantic category.action format."""
        if not self._controller:
            return ActionResult(
                success=False,
                action_type="smarthome",
                action_name=f"{category}.{action}",
                confidence=0.0,
                error="SmartHome not available",
            )

        # Map semantic actions to controller methods
        action_map = {
            ("climate", "comfort"): lambda: self._controller.set_room_temp(
                ctx.room or "Living Room", 70
            ),
            ("climate", "heat"): lambda: self._controller.set_room_temp(
                ctx.room or "Living Room", 72
            ),
            ("climate", "cool"): lambda: self._controller.set_room_temp(
                ctx.room or "Living Room", 68
            ),
            ("lights", "focus"): lambda: self._controller.set_lights(
                100, rooms=[ctx.room] if ctx.room else None
            ),
            ("lights", "relax"): lambda: self._controller.set_lights(
                40, rooms=[ctx.room] if ctx.room else None
            ),
            ("lights", "bright"): lambda: self._controller.set_lights(
                100, rooms=[ctx.room] if ctx.room else None
            ),
            ("lights", "dim"): lambda: self._controller.set_lights(
                20, rooms=[ctx.room] if ctx.room else None
            ),
            ("scene", "movie"): lambda: self._controller.movie_mode(),
            ("scene", "goodnight"): lambda: self._controller.goodnight(),
            ("audio", "play"): lambda: self._controller.spotify_play_playlist("focus"),
            ("audio", "announce"): lambda: self._controller.announce(
                ctx.parameters.get("text", ""), rooms=[ctx.room] if ctx.room else None
            ),
            ("security", "lock_all"): lambda: self._controller.lock_all(),
            ("shades", "open"): lambda: self._controller.open_shades(
                rooms=[ctx.room] if ctx.room else None
            ),
            ("shades", "close"): lambda: self._controller.close_shades(
                rooms=[ctx.room] if ctx.room else None
            ),
            ("tesla", "precondition"): lambda: self._controller.precondition_car(),
        }

        handler = action_map.get((category, action))
        if handler:
            try:
                await handler()
                return ActionResult(
                    success=True,
                    action_type="smarthome",
                    action_name=f"{category}.{action}",
                    confidence=0.8,
                    result={"category": category, "action": action, "room": ctx.room},
                    method="llm_fallback",
                )
            except Exception as e:
                return ActionResult(
                    success=False,
                    action_type="smarthome",
                    action_name=f"{category}.{action}",
                    confidence=0.0,
                    error=str(e),
                    method="llm_fallback",
                )

        return ActionResult(
            success=False,
            action_type="smarthome",
            action_name=f"{category}.{action}",
            confidence=0.0,
            error=f"Unknown semantic action: {category}.{action}",
            method="llm_fallback",
        )

    def get_stats(self) -> dict[str, Any]:
        """Get execution statistics."""
        return {
            "total_executions": self._total_executions,
            "digital_executions": self._digital_executions,
            "smarthome_executions": self._smarthome_executions,
            "meta_executions": self._meta_executions,
            "builtin_executions": self._builtin_executions,
            "llm_fallbacks": self._llm_fallbacks,
            "composio_available": self._composio is not None,
            "smarthome_available": self._controller is not None,
            "builtin_tools_available": self._tools_integration is not None,
            "llm_fallback_available": self._action_mapper is not None,
        }


# =============================================================================
# SINGLETON
# =============================================================================

_executor: UnifiedActionExecutor | None = None


def get_unified_action_executor() -> UnifiedActionExecutor:
    """Get the singleton UnifiedActionExecutor."""
    global _executor
    if _executor is None:
        _executor = UnifiedActionExecutor()
    return _executor


async def initialize_action_executor() -> UnifiedActionExecutor:
    """Initialize and return the UnifiedActionExecutor."""
    executor = get_unified_action_executor()
    await executor.initialize()
    return executor


def reset_action_executor() -> None:
    """Reset the singleton (for testing)."""
    global _executor
    _executor = None
