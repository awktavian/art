# Kagami Plugin System

Comprehensive extensibility framework for Kagami.

## Overview

The Kagami Plugin System provides a complete architecture for extending Kagami's functionality through plugins. Plugins can add custom colonies, safety filters, Forge modules, receipt processors, and more.

## Features

- **Plugin Discovery**: Automatic discovery via entry points
- **Lifecycle Management**: Init, start, stop, cleanup hooks
- **Dependency Resolution**: Topological sorting of plugin dependencies
- **Version Compatibility**: Automatic compatibility checking
- **Hook System**: Type-safe extension points
- **Capability Registry**: Discover plugins by capability
- **Health Monitoring**: Built-in health checks
- **Error Handling**: Fail-fast with clear errors

## Quick Start

### 1. Create a Plugin

```python
from kagami.plugins import BasePlugin, PluginMetadata

class MyPlugin(BasePlugin):
    @classmethod
    def get_metadata(cls):
        return PluginMetadata(
            plugin_id="my_org.my_plugin",
            name="My Plugin",
            version="1.0.0",
            description="My custom plugin",
            author="My Organization",
            entry_point="my_package.plugin:MyPlugin",
        )

    def on_init(self):
        print("Plugin initialized")

    def on_cleanup(self):
        print("Plugin cleaned up")
```

### 2. Load Plugin

```python
from kagami.plugins import get_plugin_manager

manager = get_plugin_manager()
plugin = MyPlugin()
manager.register(plugin)
manager.load("my_org.my_plugin")
manager.start("my_org.my_plugin")
```

### 3. Use Hooks

```python
from kagami.plugins import HookType, get_hook_registry

def my_hook(ctx):
    print(f"Task: {ctx.get('task')}")
    return ctx

registry = get_hook_registry()
registry.register_hook(HookType.PRE_ACTION, my_hook, plugin_id="my_org.my_plugin")
```

## Plugin Types

### 1. Custom Colony

Add specialized agent colonies to the unified organism.

**Example:** [examples/custom_colony/](examples/custom_colony/)

```python
from kagami.plugins import BasePlugin
from kagami.core.unified_agents.agents.base_colony_agent import BaseColonyAgent

class MyColonyAgent(BaseColonyAgent):
    def get_system_prompt(self):
        return "You are a specialized colony..."

    def process_with_catastrophe(self, task, context):
        # Implementation
        pass
```

### 2. Custom Safety Filter

Add domain-specific safety checks to the CBF system.

**Example:** [examples/custom_safety/](examples/custom_safety/)

```python
class MySafetyFilter:
    def check_safety(self, content, context):
        # Custom safety logic
        h_x = 1.0 - threat_level
        return {"safe": h_x >= 0.0, "h_x": h_x, "threats": []}
```

### 3. Custom Forge Module

Add new content generation capabilities.

**Example:** [examples/custom_forge/](examples/custom_forge/)

```python
class MyGeneratorModule:
    def generate(self, params):
        # Custom generation logic
        return {"content": "generated"}
```

## Integration Points

The plugin system provides hooks for integrating with Kagami's core:

- **Colony Hooks**: Pre/post action, colony registration
- **Safety Hooks**: Pre/post safety check, safety filter
- **Forge Hooks**: Pre/post generation, module registration
- **Receipt Hooks**: Pre/post emission, receipt processing
- **World Model Hooks**: Pre/post prediction
- **Routing Hooks**: Pre/post routing

See [docs/INTEGRATION_POINTS.md](docs/INTEGRATION_POINTS.md) for details.

## Architecture

```
Plugin System
├── Plugin Manager (manager.py)
│   ├── Discovery (entry points)
│   ├── Loading (dependency resolution)
│   ├── Lifecycle (init, start, stop, cleanup)
│   └── Health checks
├── Base Plugin (base.py)
│   ├── Metadata
│   ├── Lifecycle hooks
│   └── Configuration
├── Hook Registry (hooks.py)
│   ├── Hook types
│   ├── Handler registration
│   └── Hook execution
└── Plugin Registry (registry.py)
    ├── Capability index
    ├── Metadata storage
    └── Query interface
```

## Directory Structure

```
kagami/plugins/
├── __init__.py           # Main exports
├── base.py               # BasePlugin class
├── manager.py            # PluginManager
├── hooks.py              # Hook system
├── registry.py           # Plugin registry
├── docs/                 # Documentation
│   ├── INTEGRATION_POINTS.md
│   ├── PLUGIN_DEVELOPMENT.md
│   └── API_REFERENCE.md
└── examples/             # Example plugins
    ├── custom_colony/    # Colony example
    ├── custom_safety/    # Safety filter example
    └── custom_forge/     # Forge module example
```

## Documentation

- **[Plugin Development Guide](docs/PLUGIN_DEVELOPMENT.md)**: Complete guide to creating plugins
- **[Integration Points](docs/INTEGRATION_POINTS.md)**: Available hooks and integration points
- **[API Reference](docs/API_REFERENCE.md)**: Complete API documentation

## Examples

Three complete example plugins are provided:

1. **Architect Colony** (`examples/custom_colony/`)
   - Custom 8th colony for system architecture
   - Demonstrates colony agent integration
   - Shows catastrophe dynamics

2. **Code Security Filter** (`examples/custom_safety/`)
   - Security checks for code operations
   - Demonstrates CBF integration
   - Shows safety hook usage

3. **Document Generator** (`examples/custom_forge/`)
   - Technical document generation
   - Demonstrates Forge integration
   - Shows generation hooks

## Testing

```bash
# Run plugin system tests
pytest tests/plugins/

# Run example plugin tests
pytest tests/plugins/test_examples.py
```

## Best Practices

1. **Single Responsibility**: One plugin, one purpose
2. **Clear Metadata**: Complete and accurate plugin metadata
3. **Minimal Dependencies**: Minimize plugin dependencies
4. **Fail Fast**: Surface errors clearly, don't hide failures
5. **Fast Hooks**: Keep hook handlers under 10ms
6. **Test Coverage**: > 80% test coverage
7. **Documentation**: Clear README and examples

## Contributing

We welcome plugin contributions! To contribute:

1. Fork the repository
2. Create your plugin in `kagami/plugins/examples/`
3. Add tests in `tests/plugins/`
4. Update documentation
5. Submit a pull request

## Support

- GitHub Issues: https://github.com/KagamiOS/kagami/issues
- Documentation: https://docs.awkronos.com/plugins
- Community: https://discord.gg/kagami

## License

See [LICENSE](../../LICENSE) for details.

## Version

Current version: 1.0.0

Last updated: December 28, 2025
