"""Test plugin system core functionality.

Tests cover:
- Plugin manager lifecycle
- Hook registration and execution
- Plugin registry
- Example plugins

Created: December 28, 2025
"""

import pytest

from kagami.plugins import (
    BasePlugin,
    PluginMetadata,
    PluginState,
    HealthCheckResult,
    HookType,
    HookContext,
    get_plugin_manager,
    get_hook_registry,
    get_plugin_registry,
    reset_plugin_manager,
    reset_hook_registry,
    reset_plugin_registry,
)


# Test plugin implementation
class TestPlugin(BasePlugin):
    """Simple test plugin."""

    def __init__(self):
        super().__init__()
        self.initialized = False
        self.started = False
        self.stopped = False
        self.cleaned_up = False

    @classmethod
    def get_metadata(cls) -> PluginMetadata:
        return PluginMetadata(
            plugin_id="test.plugin",
            name="Test Plugin",
            version="1.0.0",
            description="Plugin for testing",
            author="Test Author",
            entry_point="test_plugin:TestPlugin",
            capabilities=["test_capability"],
        )

    def on_init(self) -> None:
        self.initialized = True

    def on_start(self) -> None:
        self.started = True

    def on_stop(self) -> None:
        self.stopped = True

    def on_cleanup(self) -> None:
        self.cleaned_up = True

    def health_check(self) -> HealthCheckResult:
        return HealthCheckResult(
            healthy=self.initialized,
            status="ok" if self.initialized else "error",
            details={"initialized": self.initialized},
        )


# Fixtures
@pytest.fixture
def clean_plugin_system():
    """Reset plugin system before each test."""
    reset_plugin_manager()
    reset_hook_registry()
    reset_plugin_registry()
    yield
    reset_plugin_manager()
    reset_hook_registry()
    reset_plugin_registry()


@pytest.fixture
def plugin_manager(clean_plugin_system):
    """Get fresh plugin manager."""
    return get_plugin_manager()


@pytest.fixture
def hook_registry(clean_plugin_system):
    """Get fresh hook registry."""
    return get_hook_registry()


@pytest.fixture
def plugin_registry(clean_plugin_system):
    """Get fresh plugin registry."""
    return get_plugin_registry()


# Plugin Manager Tests
class TestPluginManager:
    """Test plugin manager functionality."""

    def test_plugin_registration(self, plugin_manager):
        """Test plugin registration."""
        plugin = TestPlugin()
        plugin_manager.register(plugin)

        assert plugin.state == PluginState.REGISTERED

    def test_plugin_load(self, plugin_manager):
        """Test plugin loading."""
        plugin = TestPlugin()
        plugin_manager.register(plugin)

        result = plugin_manager.load("test.plugin")

        assert result.success
        assert plugin.initialized
        assert plugin.state == PluginState.INITIALIZED

    def test_plugin_start(self, plugin_manager):
        """Test plugin start."""
        plugin = TestPlugin()
        plugin_manager.register(plugin)
        plugin_manager.load("test.plugin")

        success = plugin_manager.start("test.plugin")

        assert success
        assert plugin.started
        assert plugin.state == PluginState.STARTED

    def test_plugin_stop(self, plugin_manager):
        """Test plugin stop."""
        plugin = TestPlugin()
        plugin_manager.register(plugin)
        plugin_manager.load("test.plugin")
        plugin_manager.start("test.plugin")

        success = plugin_manager.stop("test.plugin")

        assert success
        assert plugin.stopped
        assert plugin.state == PluginState.INITIALIZED

    def test_plugin_unload(self, plugin_manager):
        """Test plugin unload."""
        plugin = TestPlugin()
        plugin_manager.register(plugin)
        plugin_manager.load("test.plugin")

        success = plugin_manager.unload("test.plugin")

        assert success
        assert plugin.cleaned_up
        assert plugin.state == PluginState.UNLOADED

    def test_plugin_health_check(self, plugin_manager):
        """Test plugin health check."""
        plugin = TestPlugin()
        plugin_manager.register(plugin)
        plugin_manager.load("test.plugin")

        health = plugin_manager.check_health("test.plugin")

        assert health["healthy"]
        assert health["state"] == "initialized"

    def test_plugin_get(self, plugin_manager):
        """Test getting plugin instance."""
        plugin = TestPlugin()
        plugin_manager.register(plugin)
        plugin_manager.load("test.plugin")

        retrieved = plugin_manager.get_plugin("test.plugin")

        assert retrieved is plugin

    def test_plugin_metadata_get(self, plugin_manager):
        """Test getting plugin metadata."""
        plugin = TestPlugin()
        plugin_manager.register(plugin)

        metadata = plugin_manager.get_metadata("test.plugin")

        assert metadata is not None
        assert metadata.plugin_id == "test.plugin"
        assert metadata.name == "Test Plugin"


# Hook Registry Tests
class TestHookRegistry:
    """Test hook registry functionality."""

    def test_hook_registration(self, hook_registry):
        """Test hook registration."""

        def my_hook(ctx):
            return ctx

        hook_registry.register_hook(HookType.PRE_ACTION, my_hook, plugin_id="test")

        hooks = hook_registry.list_hooks(HookType.PRE_ACTION)
        assert "test" in hooks[HookType.PRE_ACTION.value]

    def test_hook_unregistration(self, hook_registry):
        """Test hook unregistration."""

        def my_hook(ctx):
            return ctx

        hook_registry.register_hook(HookType.PRE_ACTION, my_hook, plugin_id="test")
        removed = hook_registry.unregister_hook(HookType.PRE_ACTION, "test")

        assert removed == 1
        hooks = hook_registry.list_hooks(HookType.PRE_ACTION)
        assert len(hooks[HookType.PRE_ACTION.value]) == 0

    def test_hook_call(self, hook_registry):
        """Test hook execution."""
        called = []

        def my_hook(ctx):
            called.append(True)
            ctx.set("modified", True)
            return ctx

        hook_registry.register_hook(HookType.PRE_ACTION, my_hook, plugin_id="test")

        ctx = HookContext(HookType.PRE_ACTION, {"task": "test"})
        result = hook_registry.call_hook(HookType.PRE_ACTION, ctx)

        assert len(called) == 1
        assert result.get("modified") is True

    def test_hook_chain(self, hook_registry):
        """Test hook chaining."""

        def hook1(ctx):
            ctx.set("hook1", True)
            return ctx

        def hook2(ctx):
            ctx.set("hook2", True)
            return ctx

        hook_registry.register_hook(HookType.PRE_ACTION, hook1, plugin_id="test1")
        hook_registry.register_hook(HookType.PRE_ACTION, hook2, plugin_id="test2")

        ctx = HookContext(HookType.PRE_ACTION, {})
        result = hook_registry.call_hook(HookType.PRE_ACTION, ctx)

        assert result.get("hook1") is True
        assert result.get("hook2") is True

    def test_hook_error_handling(self, hook_registry):
        """Test hook error handling."""

        def failing_hook(ctx):
            raise ValueError("Test error")

        def succeeding_hook(ctx):
            ctx.set("success", True)
            return ctx

        hook_registry.register_hook(HookType.PRE_ACTION, failing_hook, plugin_id="fail")
        hook_registry.register_hook(HookType.PRE_ACTION, succeeding_hook, plugin_id="success")

        ctx = HookContext(HookType.PRE_ACTION, {})
        result = hook_registry.call_hook(HookType.PRE_ACTION, ctx)

        # Succeeding hook should still run despite failing hook
        assert result.get("success") is True


# Plugin Registry Tests
class TestPluginRegistry:
    """Test plugin registry functionality."""

    def test_plugin_registration(self, plugin_registry):
        """Test plugin registration in registry."""
        plugin = TestPlugin()
        plugin_registry.register(plugin)

        assert plugin_registry.get_plugin("test.plugin") is plugin

    def test_capability_query(self, plugin_registry):
        """Test capability querying."""
        plugin = TestPlugin()
        plugin_registry.register(plugin)

        plugins = plugin_registry.get_plugins_by_capability("test_capability")

        assert "test.plugin" in plugins

    def test_has_capability(self, plugin_registry):
        """Test capability existence check."""
        plugin = TestPlugin()
        plugin_registry.register(plugin)

        assert plugin_registry.has_capability("test_capability")
        assert not plugin_registry.has_capability("nonexistent")

    def test_list_capabilities(self, plugin_registry):
        """Test listing all capabilities."""
        plugin = TestPlugin()
        plugin_registry.register(plugin)

        capabilities = plugin_registry.list_capabilities()

        assert "test_capability" in capabilities


# Integration Tests
class TestPluginIntegration:
    """Test full plugin integration."""

    def test_plugin_full_lifecycle(self, plugin_manager, hook_registry):
        """Test complete plugin lifecycle."""
        hook_called = []

        class IntegrationPlugin(BasePlugin):
            @classmethod
            def get_metadata(cls):
                return PluginMetadata(
                    plugin_id="integration.plugin",
                    name="Integration Plugin",
                    version="1.0.0",
                    description="Integration test",
                    author="Test",
                    entry_point="test:IntegrationPlugin",
                )

            def on_init(self):
                hook_registry.register_hook(
                    HookType.PRE_ACTION,
                    self._my_hook,
                    plugin_id=self.get_metadata().plugin_id,
                )

            def on_cleanup(self):
                hook_registry.unregister_hook(
                    HookType.PRE_ACTION, self.get_metadata().plugin_id
                )

            def _my_hook(self, ctx):
                hook_called.append(True)
                return ctx

        # Register and load
        plugin = IntegrationPlugin()
        plugin_manager.register(plugin)
        plugin_manager.load("integration.plugin")
        plugin_manager.start("integration.plugin")

        # Call hook
        ctx = HookContext(HookType.PRE_ACTION, {})
        hook_registry.call_hook(HookType.PRE_ACTION, ctx)

        # Verify hook was called
        assert len(hook_called) == 1

        # Unload
        plugin_manager.unload("integration.plugin")

        # Verify hook was unregistered
        hooks = hook_registry.list_hooks(HookType.PRE_ACTION)
        assert len(hooks[HookType.PRE_ACTION.value]) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
