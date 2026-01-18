# Computer Control Skill

Full computer control via three-tier architecture.

## Tiers

| Tier | Technology | Use When |
|------|------------|----------|
| **1: Host** | Peekaboo MCP | Control my own Mac apps |
| **2: Sandboxed** | CUA/Lume | Untrusted code, agent loops |
| **3: Multi-OS** | Parallels | Windows/Linux automation |

## Tier 1: Peekaboo (Host macOS)

**Best for:** Direct control of Tim's Mac.

### MCP Tools

| Tool | Purpose |
|------|---------|
| `peekaboo_screenshot` | Capture screen/window/app |
| `peekaboo_click` | Click by coordinates or label |
| `peekaboo_type` | Type text |
| `peekaboo_scroll` | Scroll direction |
| `peekaboo_hotkey` | Keyboard shortcuts |
| `peekaboo_see` | Get accessibility tree |

### CLI Usage (VERIFIED Dec 30, 2025)

```bash
# Screenshot
peekaboo image --mode screen --path /tmp/screen.png

# Screenshot specific app window
peekaboo image --mode window --app Safari --path /tmp/safari.png

# Click at coordinates
peekaboo click --x 100 --y 200

# Double-click
peekaboo click --x 100 --y 200 --clicks 2

# Right-click
peekaboo click --x 100 --y 200 --button right

# Type text
peekaboo type "Hello, World!"

# Keyboard shortcut
peekaboo hotkey --modifiers cmd --key c
peekaboo key return

# Get accessibility tree (use 'see' not 'text')
peekaboo see --app Finder
peekaboo see --app Finder --json
peekaboo see --mode frontmost
```

### Python (via HAL)

```python
from kagami_hal.adapters.vm import PeekabooAdapter

adapter = PeekabooAdapter()
await adapter.initialize()

# Screenshot
png_bytes = await adapter.screenshot()

# Click
await adapter.click(100, 200)
await adapter.click_element("Submit", app="Safari")

# Type
await adapter.type_text("Hello")

# Hotkey
await adapter.hotkey("cmd", "c")  # Copy
await adapter.hotkey("cmd", "v")  # Paste

# Accessibility
tree = await adapter.get_accessibility_tree("Finder")
element = await adapter.find_element(label="Open")
```

## Tier 2: CUA/Lume (Sandboxed macOS)

**Best for:** Untrusted operations, agent loops, testing.

### Installation (VERIFIED Dec 30, 2025)

```bash
# Option 1: Install via Homebrew
brew install trycua/tap/lume

# Option 2: Manual binary install (if brew fails)
curl -LO https://github.com/trycua/cua/releases/latest/download/lume-macos-aarch64.tar.gz
tar -xzf lume-macos-aarch64.tar.gz
chmod +x lume && mv lume ~/.local/bin/

# Pull macOS image (choose one):
lume pull macos-sequoia-cua:latest    # 24GB - Full CUA support (recommended)
lume pull macos-sequoia-xcode:latest  # 22GB - With Xcode CLI tools
lume pull macos-sequoia-vanilla:latest # 20GB - Minimal base image

# Image will be named macos-sequoia-cua_latest after pull

# Optional: Python libraries for programmatic control
pip install cua-computer cua-agent[all]
```

### Available CUA Images

| Image | Size | Description |
|-------|------|-------------|
| `macos-sequoia-cua` | 24GB | Full Computer interface support (recommended) |
| `macos-sequoia-xcode` | 22GB | Xcode CLI tools pre-installed |
| `macos-sequoia-vanilla` | 20GB | Minimal base macOS Sequoia |

**Note:** All images have SSH pre-configured with default password `lume`. Change after first login.

### CLI Usage (VERIFIED Dec 30, 2025)

```bash
# List VMs
lume ls

# Start VM (with display)
lume run macos-sequoia-cua_latest

# Start VM (headless - no window)
lume run macos-sequoia-cua_latest --no-display

# Stop VM (closes window)
lume stop macos-sequoia-cua_latest

# Snapshots require cua-computer integration
```

### Python (via HAL — RECOMMENDED)

```python
import asyncio
from kagami_hal.adapters.vm import CUALumeAdapter

async def main():
    vm = CUALumeAdapter()
    await vm.initialize()

    # Start VM (headless = no display/audio on host)
    await vm.start(headless=True, wait_for_ssh=True)

    # Execute commands (via SSH - fast!)
    result = await vm.execute("sw_vers")
    print(f"macOS {result.stdout}")
    print(f"Duration: {result.duration_ms:.0f}ms")

    # Take screenshot
    screenshot = await vm.screenshot()
    with open("/tmp/screenshot.png", "wb") as f:
        f.write(screenshot)

    # Open Chrome with PERSISTENT PROFILE (preserves logins!)
    await vm.open_chrome("https://example.com", restore_profile=True)
    await asyncio.sleep(2)

    # Run AppleScript
    result = await vm.run_applescript(
        'tell application "Safari" to get URL of front document'
    )
    print(f"Current URL: {result.stdout}")

    # Copy files to/from VM
    await vm.copy_to_vm("/local/file.txt", "/tmp/file.txt")
    await vm.copy_from_vm("/tmp/result.txt", "/local/result.txt")

    # Get VM info
    print(f"VM IP: {vm.vm_ip}")
    print(f"VNC: {vm.vnc_url}")

    # ALWAYS save Chrome profile before stopping!
    await vm.stop_and_save(save_chrome=True)

asyncio.run(main())
```

### Chrome Profile Management (NEW Jan 4, 2026)

**Profile saved to:** `~/.kagami/vm_chrome_profile/chrome_profile.tar.gz`

**Preserves:** cookies, logins, extensions, settings, history

```python
# Open Chrome with persistent profile (restores from backup)
await vm.open_chrome("https://example.com", restore_profile=True)

# Manually save profile (before stopping VM)
await vm.save_chrome_profile()
await vm.stop()

# OR use convenience method (RECOMMENDED)
await vm.stop_and_save(save_chrome=True)

# Custom profile path
await vm.open_chrome(url, restore_profile=True, profile_path="~/.kagami/my_profile")
await vm.stop_and_save(save_chrome=True, profile_path="~/.kagami/my_profile")
```

**⚠️ ALWAYS call `stop_and_save()` to preserve browser state!**

### Python (via CUA — Optional)

```python
# Only if you install: pip install cua-computer cua-agent[all]
from computer import Computer
from agent import ComputerAgent, LLM, AgentLoop, LLMProvider

# Direct control
async with Computer(os_type="macos", display="1920x1080") as vm:
    await vm.screenshot()
    await vm.click(100, 200)
    await vm.type("Hello")

# With agent
async with Computer(os_type="macos") as vm:
    agent = ComputerAgent(
        computer=vm,
        loop=AgentLoop.ANTHROPIC,
        model=LLM(provider=LLMProvider.ANTHROPIC)
    )
    async for result in agent.run("Open Safari and go to github.com"):
        print(result)
```

## Tier 3: Parallels (Multi-OS)

**Best for:** Windows/Linux automation, cross-platform testing.

### CLI Usage (VERIFIED Dec 30, 2025)

```bash
# List VMs
prlctl list -a

# Start/Resume/Stop (NOTE: no headless option, use suspend to close window)
prlctl start "Gaming"           # Start from stopped
prlctl resume "Gaming"          # Resume from suspended
prlctl suspend "Gaming"         # Suspend (closes window)
prlctl stop "Gaming"            # Full stop

# Execute command
prlctl exec "Gaming" cmd /c "dir C:\\"
prlctl exec "Gaming" cmd /c "echo Hello && ver"

# Screenshot
prlctl capture "Gaming" --file /tmp/windows.png

# Snapshot
prlctl snapshot "Gaming" -n "clean-state"
prlctl snapshot-switch "Gaming" -n "clean-state"
```

### Python (via HAL)

```python
from kagami_hal.adapters.vm import ParallelsAdapter

adapter = ParallelsAdapter("Windows-11")
await adapter.initialize()
await adapter.start()

# Execute Windows command
result = await adapter.execute("dir C:\\Users")
print(result.stdout)

# Screenshot
screenshot = await adapter.screenshot()

# Snapshot
await adapter.create_snapshot("fresh-install")
```

## VM Pool

For concurrent automation across multiple VMs.

```python
from kagami_hal.adapters.vm import get_vm_pool, PoolConfig, OSType

# Configure pool
pool = await get_vm_pool(PoolConfig(
    max_vms=4,
    default_os=OSType.MACOS,
    auto_restore_snapshot="clean-state",
))

# Acquire and auto-release
async with pool.acquire() as vm:
    await vm.screenshot()
    await vm.click(100, 200)

# Acquire specific OS
async with pool.acquire(os_type=OSType.WINDOWS) as vm:
    await vm.execute("ipconfig")

# Parallel automation
async def task(pool, task_id):
    async with pool.acquire() as vm:
        result = await vm.execute(f"echo Task {task_id}")
        return result.stdout

results = await asyncio.gather(*[
    task(pool, i) for i in range(4)
])
```

## Common Patterns

### Take Screenshot and Analyze

```python
# Tier 1
screenshot = await adapter.screenshot()
# Save or analyze with vision model

# With MCP
# Use peekaboo_screenshot tool, then analyze image
```

### Click Button by Label

```python
# Tier 1: Native accessibility
await adapter.click_element("Submit", app="Safari")

# CLI
peekaboo click --on "Submit" --app Safari
```

### Fill Form

```python
# Click field, then type
await adapter.click_element("Email", app="Safari")
await adapter.type_text("user@example.com")
await adapter.press("tab")
await adapter.type_text("password123")
await adapter.click_element("Sign In")
```

### Keyboard Shortcuts

```python
# Copy-paste
await adapter.hotkey("cmd", "a")  # Select all
await adapter.hotkey("cmd", "c")  # Copy
await adapter.click(200, 300)     # Click destination
await adapter.hotkey("cmd", "v")  # Paste

# Save
await adapter.hotkey("cmd", "s")

# Undo
await adapter.hotkey("cmd", "z")
```

### Launch and Control App

```python
# Launch
await adapter.launch_app("Safari")
await asyncio.sleep(1)  # Wait for launch

# Interact
await adapter.hotkey("cmd", "l")  # Focus URL bar
await adapter.type_text("https://github.com")
await adapter.press("enter")
```

## Safety

All computer control actions are subject to h(x) >= 0:

- **Tier 1**: High trust (Tim only), no isolation
- **Tier 2/3**: Full VM isolation, safe for untrusted code

### Forbidden Patterns

Actions blocked by CBF:

- `rm -rf /` - Destructive commands
- `sudo shutdown` - System shutdown
- Password/credential access on Tier 1

### Best Practices

1. Use Tier 2/3 for untrusted operations
2. Create snapshots before risky actions
3. Restore to clean state after use
4. Log all actions for audit

## Key Files

| File | Purpose |
|------|---------|
| `packages/kagami_hal/adapters/vm/` | HAL VM adapters |
| `~/.cursor/mcp.json` | MCP server config |
| `.cursor/rules/execution.mdc` | Execution patterns |

## Optimal Setup Guide

### Tier 1: Peekaboo (Immediate - 5 minutes)

**Already installed.** Verify with:
```bash
peekaboo permissions  # Should show "Granted" for both
peekaboo image --mode screen --path /tmp/test.png  # Test screenshot
```

**Optimal settings:**
- Enable "Reduce motion" in Accessibility for faster UI response
- Consider keyboard shortcut customizations for frequent actions

### Tier 2: CUA/Lume (UPGRADED Jan 4, 2026)

**Current VM:** `macos-sequoia-cua_latest` (26GB, macOS 15.4.1)

```bash
# Check status
lume ls

# Start VM (with display)
lume run macos-sequoia-cua_latest

# Start VM (headless - no window, no audio to host)
lume run macos-sequoia-cua_latest --no-display

# Stop VM (closes window properly)
lume stop macos-sequoia-cua_latest
```

**Verified features (Jan 4, 2026):**
- ✅ VM starts and runs (97% native performance)
- ✅ VNC access available (vnc://...)
- ✅ Headless mode works (--no-display)
- ✅ SSH execution via sshpass (user: lume, pass: lume)
- ✅ File transfer via SCP
- ✅ Screenshots via screencapture
- ✅ AppleScript execution
- ✅ Browser automation via `open -a Safari`
- ❌ CUA Python libraries (optional, SSH is better)

**SSH Credentials:** `lume:lume` (default for all Lume VMs)

**Dependencies installed:**
- `brew install trycua/tap/lume`
- `brew install hudochenkov/sshpass/sshpass`

### Tier 3: Parallels (VERIFIED Dec 30, 2025)

**Current VMs:**
```bash
prlctl list -a
# Gaming (Windows 11) - suspended
```

**VM Specs:** "Gaming" (16 CPUs, 128GB RAM, 256GB disk)

**Verified features:**
- ✅ Resume from suspended
- ✅ Execute commands in guest
- ✅ Screenshot capture
- ✅ Suspend (closes window properly)

### Environment Variables

Add to your shell profile for optimal integration:

```bash
# ~/.zshrc or ~/.bashrc
export KAGAMI_VM_TIER_1_ENABLED=true
export KAGAMI_VM_TIER_2_VM="macos-sequoia-cua_latest"
export KAGAMI_VM_TIER_3_VM="Gaming"
export KAGAMI_VM_POOL_MAX=4
```

## Related Skills

- `smarthome/` - Physical device control
- `composio/` - Digital API control
