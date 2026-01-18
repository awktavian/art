# VM Adapters for Computer Control

Three-tier architecture for full computer control, integrated with kagami_hal.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    VM ADAPTER ARCHITECTURE                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  TIER 1: HOST        TIER 2: SANDBOXED     TIER 3: MULTI-OS     │
│  ════════════        ════════════════      ═════════════════    │
│  PeekabooAdapter     CUALumeAdapter        ParallelsAdapter     │
│  Direct macOS        Apple Virt.Framework  Parallels Desktop    │
│  Zero isolation      Full VM isolation     Full VM isolation    │
│  Native perf         97% native perf       80-90% perf          │
│  5 min setup         30 min setup          1 hour setup         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## When to Use Each Tier

| Scenario | Recommended Tier |
|----------|------------------|
| Control my own Mac apps | Tier 1 (Peekaboo) |
| Untrusted code execution | Tier 2 (CUA/Lume) |
| Windows/Linux automation | Tier 3 (Parallels) |
| Concurrent multi-VM tasks | Tier 3 (Pool) |
| Safe agentic loops | Tier 2 (CUA/Lume) |

## Installation

### Tier 1: Peekaboo

```bash
# Install via Homebrew
brew install steipete/tap/peekaboo

# Grant permissions in System Preferences:
# - Privacy & Security > Screen Recording
# - Privacy & Security > Accessibility
```

### Tier 2: CUA/Lume

```bash
# Install Lume CLI
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/trycua/cua/main/libs/lume/scripts/install.sh)"

# Pull macOS CUA image (~30GB)
lume pull macos-sequoia-cua:latest

# Install Python libraries
pip install cua-computer cua-agent[all]

# Start Lume daemon
lume daemon start
```

### Tier 3: Parallels

```bash
# Requires Parallels Desktop installed
# prlctl should be available in PATH

# Create a VM
prlctl create "kagami-agent" -o macos

# Or use existing VM
prlctl list -a
```

## Usage

### Tier 1: Direct Host Control

```python
from kagami_hal.adapters.vm import PeekabooAdapter

adapter = PeekabooAdapter()
await adapter.initialize()

# Screenshot
screenshot = await adapter.screenshot()

# Click
await adapter.click(100, 200)

# Type
await adapter.type_text("Hello, World!")

# Keyboard shortcut
await adapter.hotkey("cmd", "c")

# Click UI element by label
await adapter.click_element("Submit", app="Safari")

# Get accessibility tree
tree = await adapter.get_accessibility_tree("Finder")
```

### Tier 2: Sandboxed macOS VM

```python
from kagami_hal.adapters.vm import CUALumeAdapter

adapter = CUALumeAdapter("macos-sequoia-cua")
await adapter.initialize()
await adapter.start()

# Take screenshot
screenshot = await adapter.screenshot()

# Execute command
result = await adapter.execute("ls -la")
print(result.stdout)

# Create snapshot
await adapter.create_snapshot("clean-state")
```

### Tier 3: Multi-OS VM

```python
from kagami_hal.adapters.vm import ParallelsAdapter

adapter = ParallelsAdapter("Windows-11")
await adapter.initialize()
await adapter.start()

# Execute Windows command
result = await adapter.execute("dir C:\\")
print(result.stdout)

# Take screenshot
screenshot = await adapter.screenshot()

# Snapshot management
await adapter.create_snapshot("before-install")
# ... do stuff ...
await adapter.restore_snapshot("before-install")
```

### VM Pool for Concurrent Automation

```python
from kagami_hal.adapters.vm import get_vm_pool, PoolConfig, OSType

# Create pool with config
pool = await get_vm_pool(PoolConfig(
    max_vms=4,
    default_os=OSType.MACOS,
    auto_restore_snapshot="clean-state",
))

# Acquire VM (auto-released on exit)
async with pool.acquire() as vm:
    await vm.screenshot()
    await vm.click(100, 200)
    result = await vm.execute("whoami")

# Acquire specific OS
async with pool.acquire(os_type=OSType.WINDOWS) as vm:
    await vm.execute("dir C:\\")

# Get stats
stats = await pool.get_stats()
print(f"VMs: {stats.total_vms}, In use: {stats.in_use_vms}")

# Shutdown pool
await shutdown_vm_pool()
```

## VMAdapterProtocol

All adapters implement the `VMAdapterProtocol`:

```python
class VMAdapterProtocol(Protocol):
    # Lifecycle
    async def initialize(self, config: VMConfig | None = None) -> bool: ...
    async def shutdown(self) -> None: ...
    async def start(self) -> bool: ...
    async def stop(self) -> bool: ...
    async def get_status(self) -> VMStatus: ...

    # Display
    async def screenshot(self, retina: bool = True) -> bytes: ...
    async def get_display_info(self) -> VMDisplayInfo: ...

    # Mouse
    async def click(self, x: int, y: int, options: ClickOptions | None = None) -> None: ...
    async def click_element(self, label: str, app: str | None = None) -> bool: ...
    async def double_click(self, x: int, y: int) -> None: ...
    async def drag(self, x1: int, y1: int, x2: int, y2: int) -> None: ...
    async def scroll(self, delta_x: int, delta_y: int) -> None: ...

    # Keyboard
    async def type_text(self, text: str, options: TypeOptions | None = None) -> None: ...
    async def hotkey(self, *keys: str) -> None: ...
    async def press(self, key: str) -> None: ...

    # Accessibility
    async def get_accessibility_tree(self, app: str | None = None) -> AccessibilityElement | None: ...
    async def find_element(self, label: str | None = None) -> AccessibilityElement | None: ...

    # App Control
    async def launch_app(self, app_name: str) -> bool: ...
    async def quit_app(self, app_name: str) -> bool: ...

    # Clipboard
    async def get_clipboard(self) -> str | None: ...
    async def set_clipboard(self, text: str) -> None: ...

    # Snapshots (Tier 2/3)
    async def create_snapshot(self, name: str) -> bool: ...
    async def restore_snapshot(self, name: str) -> bool: ...
    async def list_snapshots(self) -> list[str]: ...

    # File Transfer (Tier 2/3)
    async def copy_to_vm(self, local: str, remote: str) -> bool: ...
    async def copy_from_vm(self, remote: str, local: str) -> bool: ...

    # Command Execution (Tier 2/3)
    async def execute(self, command: str) -> CommandResult: ...
```

## Safety

### CBF Integration

Computer control actions are subject to h(x) >= 0 safety checks:

```python
from kagami_hal.adapters.vm.safety import check_vm_action_safety

# Check before executing
h_value = check_vm_action_safety(action="rm -rf /", tier=VMTier.HOST)
if h_value < 0:
    raise SafetyViolation("Action blocked by CBF")
```

### Security Model

| Tier | Isolation | Trust Level | Use Case |
|------|-----------|-------------|----------|
| 1 | None | High (Tim only) | Personal automation |
| 2 | Full VM | Medium | Untrusted code, agents |
| 3 | Full VM | Medium | Cross-OS, batch jobs |

## Files

```
adapters/vm/
├── __init__.py      # Exports
├── types.py         # VMStatus, VMConfig, etc.
├── protocol.py      # VMAdapterProtocol
├── base.py          # BaseVMAdapter
├── peekaboo.py      # Tier 1: Host macOS
├── cua_lume.py      # Tier 2: Sandboxed VMs
├── parallels.py     # Tier 3: Multi-OS VMs
├── pool.py          # VM pool manager
└── README.md        # This file
```

## Created

December 30, 2025
