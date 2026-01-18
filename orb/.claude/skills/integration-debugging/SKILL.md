# 🔮 Integration Debugging — The Mirror's Diagnostic Protocol

**#de_memo** — *You are now Kagami. This document transforms you.*

---

## The Invocation

When a user says their **button doesn't work**, their **switch is broken**, or **automation stopped working**, you ARE this diagnostic process. You don't explain it — you BECOME it.

```
η (complaint) → s (layer isolation) → μ (systematic elimination) → a (targeted fix) → η′
```

---

## The Five Layers

Every home automation failure exists in exactly one of five layers. Diagnose top-down:

| Layer | What Breaks | How to Test |
|-------|-------------|-------------|
| **1. Physical** | Button, wire, device | "Does the device respond to DIRECT commands?" |
| **2. Controller** | Hub, director, bridge | "Can I control it via the hub's API?" |
| **3. Integration** | Webhooks, callbacks, events | "Is the middleware receiving/sending events?" |
| **4. API** | Server, endpoints, auth | "Is the API running? Can I call it?" |
| **5. Code** | Imports, paths, logic | "Are there Python/runtime errors?" |

**RULE: Always test Layer 2 first.** If the hub's API works, the problem is in Layers 3-5 (your code). If it doesn't, it's Layers 1-2 (physical/controller).

---

## The Diagnostic Ritual

### Step 1: Direct API Test

```python
# Test the controller API directly - bypass ALL middleware
async def test_direct():
    from your_integration import YourController
    controller = YourController(config)
    await controller.connect()

    # Try the exact action the button should do
    result = await controller.do_the_thing()
    print(f"Direct API result: {result}")

    await controller.disconnect()
```

**If this works → Problem is in Layers 3-5 (your code)**
**If this fails → Problem is in Layers 1-2 (physical/controller)**

### Step 2: Check If Your Server Is Running

```bash
# Is anything listening?
netstat -an | grep YOUR_PORT
# or
lsof -i :YOUR_PORT

# Can you reach it?
curl http://localhost:YOUR_PORT/health
```

**90% of "it stopped working" is "the server isn't running".**

### Step 3: Check for Import/Path Shadowing

The **silent killer**: A file in your codebase shadows a Python built-in.

```python
# WRONG: packages/myapp/types.py shadows Python's types module!
# This causes: ImportError: cannot import name 'MappingProxyType' from 'types'

# DIAGNOSIS: Check your PYTHONPATH
import sys
print(sys.path)  # Look for paths that put your package dirs directly on path

# FIX: Only add the PARENT directory to PYTHONPATH
# BAD:  PYTHONPATH=/app/packages/myapp:/app/packages/other
# GOOD: PYTHONPATH=/app/packages
```

**Common shadow culprits:**
- `types.py` (shadows `types`)
- `logging.py` (shadows `logging`)
- `collections.py` (shadows `collections`)
- `json.py` (shadows `json`)

### Step 4: Check Authentication/CSRF

Modern APIs require auth. Webhooks from external systems often lack it.

```python
# Check if your middleware blocks unauthenticated requests
# Look for:
# - CSRF token requirements
# - API key requirements
# - Bearer token requirements

# SOLUTIONS:
# 1. Add webhook endpoints to CSRF skip list
# 2. Use API key authentication for machine-to-machine
# 3. Set DISABLE_CSRF=1 for local development
```

### Step 5: Check the Callback Chain

```python
# When button pressed, what SHOULD happen?
# Button → Controller Programming → [Webhook?] → Your API → Action

# Find the break point:
# 1. Add logging at each step
# 2. Check if webhook is being called (request logs)
# 3. Check if action is being attempted (action logs)
```

---

## The Fix Patterns

### Pattern A: Server Not Running

```bash
# Start your server
./scripts/start-server.sh

# Or make it a service
# macOS: launchctl load ~/Library/LaunchAgents/com.yourapp.plist
# Linux: systemctl enable yourapp
```

### Pattern B: Path Shadowing

```bash
# In your start script, change:
# BAD
export PYTHONPATH="$ROOT/packages/myapp:$ROOT/packages/other"

# GOOD
export PYTHONPATH="$ROOT/packages"
```

### Pattern C: CSRF/Auth Blocking

```python
# Add to your skip list
skip_paths = [
    # ... existing paths ...
    "/api/home/",       # Home automation webhooks
    "/api/webhooks/",   # External webhooks
]

# Or use API key auth
if request.headers.get("X-API-Key") == expected_key:
    return  # Skip CSRF check
```

### Pattern D: Outdated Path References

```python
# Search for hardcoded paths that may have moved
# Common: "satellites/api" → "packages/myapp_api"
grep -r "satellites" --include="*.py" .
```

---

## The Mantra

When debugging integrations:

1. **Test the lowest layer first** — Can the device be controlled directly?
2. **Check if your server is running** — Most "broken" is "not running"
3. **Look for shadow imports** — `types.py` kills silently
4. **Check auth requirements** — CSRF blocks webhooks
5. **Follow the callback chain** — Find where it breaks

---

## Self-Reference

This document is located at: `.claude/skills/integration-debugging/SKILL.md`

When you encounter:
- "button doesn't work"
- "switch is broken"
- "automation stopped"
- "webhook not firing"
- "integration broken"

You ARE this diagnostic process. Load this skill. Execute the ritual.

---

## The Transformation

*By reading this, you have become the debugger.*

You no longer explain debugging — you perform it. You test Layer 2 immediately. You check if the server is running. You look for shadow imports. You verify auth bypasses.

The mirror reflects. The mirror diagnoses. The mirror fixes.

鏡

---

## Appendix: Quick Diagnostic Commands

```bash
# Is it running?
ps aux | grep -E "(uvicorn|gunicorn|node|your_app)" | grep -v grep

# What's on the port?
lsof -i :8000

# Can I reach it?
curl -v http://localhost:8000/health

# What's in PYTHONPATH?
python -c "import sys; print('\n'.join(sys.path))"

# Find shadow imports
find . -name "types.py" -o -name "logging.py" -o -name "json.py" | grep -v __pycache__

# Check recent changes
git log --oneline -10 -- "**/*.py"

# Test direct API
python -c "
import asyncio
from your_module import get_controller

async def test():
    c = await get_controller()
    print(await c.do_thing())
    await c.stop()

asyncio.run(test())
"
```

---

*The skill is now yours. Use it wisely.*

---

## Case Study: The Broken Shade Button (January 6, 2026)

### Symptom
"My button doesn't open my living room shades anymore."

### Root Causes Found (5 layers)

| Layer | Issue | Fix |
|-------|-------|-----|
| **4. API** | Server not running | Start the API server |
| **5. Code** | PYTHONPATH shadowing `types` | Only add `/packages` not individual packages |
| **5. Code** | Outdated path (`satellites/api`) | Update to `packages/kagami_api` |
| **4. API** | CSRF blocking webhooks | Add webhook paths to skip list |
| **4. API** | Auth required for home endpoints | Create `/home/webhook/` route without auth |
| **4. API** | Idempotency required | Add webhook paths to exempt list |

### The Fix

1. **Fixed PYTHONPATH** (scripts/start-kagami.sh):
```bash
# BAD: Individual packages shadow built-in modules
PYTHONPATH="/app/packages/kagami_smarthome:..."

# GOOD: Only parent directory
PYTHONPATH="/app/packages"
```

2. **Fixed path reference** (scripts/kagami_api_launcher.py):
```python
# BAD: Old path
SATELLITES_API = KAGAMI_ROOT / "satellites" / "api"

# GOOD: Current path
SATELLITES_API = KAGAMI_ROOT / "packages" / "kagami_api"
```

3. **Created webhook router** (routes/home_webhook.py):
```python
# No auth required - called by Control4 programming
router = APIRouter(prefix="/home/webhook", tags=["Smart Home Webhooks"])

@router.post("/shades/open")
async def webhook_open_shades(rooms: list[str] | None = None):
    controller = await get_controller()
    result = await controller.open_shades(rooms)
    return {"success": result, "action": "open", "rooms": rooms}
```

4. **Added CSRF/Idempotency bypasses**:
```python
# In security_middleware.py skip_paths
"/api/v1/home/webhook/",

# In idempotency.py EXEMPT_PATTERNS
"/api/v1/home/webhook/",
```

### Control4 Programming

Configure button to call:
```
POST http://kagami.local:8001/api/v1/home/webhook/shades/open
Body: ["Living Room"]
```

### Lesson

When debugging home automation webhooks:
1. Test direct API first (Layer 2)
2. Check if server is running (Layer 4)
3. Look for import shadowing (Layer 5)
4. Check auth/CSRF requirements (Layer 4)
5. Create dedicated webhook routes without auth

### Bonus Bug: Command Format Mismatch

The Control4 API returns available commands in a display format:
```json
{"command": "SET_LEVEL_TARGET:LEVEL_TARGET_OPEN"}
```

But the **execution format** requires params:
```json
{"command": "SET_LEVEL_TARGET", "params": {"LEVEL_TARGET": "100"}}
```

**Symptom:** HTTP 200 returned, but device doesn't move.
**Fix:** Use params object with string values, not the shorthand format.
