# Safety Verification Skill

Control Barrier Functions (CBF) for safety verification in Kagami.

## Core Safety Invariant

```
h(x) >= 0 always
```

This is the fundamental safety constraint. Every action, every command, every operation must maintain this invariant. If `h(x)` drops below zero, the action is blocked.

---

## What is a Control Barrier Function?

A Control Barrier Function (CBF) is a mathematical tool from control theory that guarantees safety by keeping the system within a "safe set" C.

### Mathematical Foundation (Ames et al., 2019)

**Safe Set Definition:**
```
C = {x in R^n | h(x) >= 0}
```

Where:
- `x` is the system state vector
- `h(x)` is the barrier function (a scalar)
- `C` is the set of all safe states

**CBF Constraint (Forward Invariance):**
```
sup_u [L_f h(x) + L_g h(x) * u] >= -alpha(h(x))
```

Where:
- `f(x), g(x)` are system dynamics
- `L_f h = dh/dx * f(x)` is the Lie derivative w.r.t. drift
- `L_g h = dh/dx * g(x)` is the Lie derivative w.r.t. control
- `alpha(h)` is an extended class-K function (learned)
- `u` is the control input

**Intuition:** As the state approaches the boundary (`h(x) -> 0`), the CBF progressively restricts available actions to prevent crossing into unsafe territory.

---

## Safety Zones

The barrier function value indicates safety margin:

| h(x) Value | Zone | Action | Description |
|------------|------|--------|-------------|
| > 0.5 | Safe | Proceed | Far from safety boundary |
| 0.1 - 0.5 | Caution | Verify | Approaching boundary |
| 0 - 0.1 | Buffer | Block (concurrent) | Too close for parallel ops |
| < 0 | Violation | STOP | Unsafe - action blocked |

---

## Implementation Architecture

### 3-Tier Barrier Hierarchy

```
CBFRegistry (thread-safe singleton)
    |
    +-- Tier 1: Organism barriers (system-wide)
    |   - Memory usage (psutil)
    |   - Process count (psutil)
    |   - Disk space (shutil)
    |   - Markov blanket integrity
    |
    +-- Tier 2: Colony barriers (7 colonies x behavioral constraints)
    |   - Per-colony resource limits
    |   - Colony coordination constraints
    |
    +-- Tier 3: Action barriers (operation-specific)
        - Output safety (text content)
        - Resource quotas
        - Physical action safety
```

### Key Files

| File | Purpose |
|------|---------|
| `packages/kagami/core/safety/control_barrier_function.py` | Entry point, re-exports |
| `packages/kagami/core/safety/cbf_integration.py` | Main safety pipeline |
| `packages/kagami/core/safety/optimal_cbf.py` | Learned barrier function (neural network) |
| `packages/kagami/core/safety/cbf_registry.py` | Centralized barrier registry |
| `packages/kagami/core/safety/cbf_decorators.py` | Function decorators |
| `packages/kagami/core/safety/types.py` | SafetyState, CBFResult types |
| `packages/kagami_smarthome/safety.py` | Physical action safety |

---

## How Safety Checks Work

### 1. Text/Content Safety (WildGuard + OptimalCBF)

```python
from kagami.core.safety.cbf_integration import check_cbf_for_operation

result = await check_cbf_for_operation(
    operation="user.message",
    action="process_intent",
    target="living_room",
    user_input="Turn on the fireplace"
)

if not result.safe:
    # h(x) < 0, action blocked
    raise SafetyViolationError(result.reason)
```

**Pipeline:**
1. **Exact Cache Check** (~0.01ms) - Hash lookup for identical queries
2. **Embedding Cache** (~5ms) - Semantic similarity match
3. **WildGuard LLM** (~900ms) - Full safety classification
4. **OptimalCBF** - Compute h(x) from classification

### 2. Physical Action Safety (Smart Home)

```python
from kagami_smarthome.safety import check_physical_safety, SafetyContext, PhysicalActionType

context = SafetyContext(
    action_type=PhysicalActionType.FIREPLACE_ON,
    target="fireplace",
)
result = check_physical_safety(context)

if not result.is_safe:  # h(x) < 0
    logger.warning(f"Fireplace blocked: {result.reason}")
```

**Physical Action Types:**
- `FIREPLACE_ON`, `FIREPLACE_OFF` - Gas hazard
- `TV_LOWER`, `TV_RAISE`, `TV_MOVE` - Mechanical hazard (MantelMount)
- `LOCK`, `UNLOCK` - Security hazard
- `HVAC_EXTREME` - Comfort/efficiency hazard
- `SHADE_ALL` - Bulk operations

### 3. Decorator-Based Enforcement

```python
from kagami.core.safety.cbf_decorators import enforce_cbf, enforce_tier1

# Direct barrier function
@enforce_cbf(
    cbf_func=lambda state: 0.5 - state.get('memory_pct', 0.0),
    barrier_name="memory",
    tier=1
)
def allocate_memory(self, size: int):
    self.memory += size

# Registry-based (Tier 1 = organism level)
@enforce_tier1("organism.memory")
def organism_level_operation(self):
    pass

# Violation handler instead of exception
@enforce_cbf(
    barrier_name="cpu",
    use_registry=True,
    violation_handler=lambda *args, **kwargs: gc.collect()
)
def cpu_intensive_task(self):
    pass
```

---

## Safety Checks for Smart Home Commands

### Fireplace (Gas Hazard)

The fireplace has CBF protection with automatic timeout:

```python
# In packages/kagami_smarthome/safety.py
FIREPLACE_MAX_ON_DURATION = 4 * 60 * 60  # 4 hours max

# Safety check before ignition
result = check_fireplace_safety("on")
if result.is_safe:
    start_fireplace_timer(controller)  # Auto-off after 4h
    await controller.fireplace_on()
```

**h(x) values:**
- `fireplace_on` (new ignition): h(x) = 0.6
- `fireplace_on` (already running): h(x) = 0.8
- `fireplace_off`: h(x) = 1.0 (always safe)

### Locks (Security Hazard)

```python
# Locking is generally safe
result = check_lock_safety("lock", "Front Door")  # h(x) = 0.9

# Unlocking has security implications
result = check_lock_safety("unlock", "Front Door")  # h(x) = 0.5
# Includes warning: "Security: Unlocking door"
```

### TV Mount (Mechanical Hazard)

```python
# Use presets when possible
result = check_tv_mount_safety("lower", preset=1)  # h(x) = 0.7

# Continuous movement is more dangerous
result = check_tv_mount_safety("move")  # h(x) = 0.4
# Warning: "Continuous TV movement - use presets when possible"
```

---

## Adding New Safety Constraints

### Step 1: Define the Barrier Function

A barrier function must return:
- Positive values when safe
- Zero at the safety boundary
- Negative values when unsafe

```python
def h_my_constraint(state: dict | None) -> float:
    """My custom barrier function.

    Args:
        state: Current state dict with relevant metrics

    Returns:
        h(x) value: > 0 is safe, < 0 is unsafe
    """
    threshold = 0.8  # 80% limit
    current_value = state.get("my_metric", 0.0) if state else 0.0

    # h(x) = threshold - current
    # When current < threshold: h > 0 (safe)
    # When current > threshold: h < 0 (unsafe)
    return threshold - current_value
```

### Step 2: Register with CBFRegistry

```python
from kagami.core.safety.cbf_registry import CBFRegistry

registry = CBFRegistry()  # Singleton

registry.register(
    tier=1,  # 1=organism, 2=colony, 3=action
    name="my_constraint",
    func=h_my_constraint,
    threshold=0.0,  # h(x) >= 0 to pass
    description="My custom safety constraint"
)
```

### Step 3: Use in Code

**Option A: Direct check**
```python
from kagami.core.safety.cbf_registry import get_cbf_registry

registry = get_cbf_registry()
state = {"my_metric": 0.5}

if registry.is_safe(state=state):
    execute_action()
else:
    violations = registry.get_violations(state=state)
    for v in violations:
        logger.error(f"Violated: {v['name']}, h(x)={v['h_x']}")
```

**Option B: Decorator**
```python
@enforce_cbf(barrier_name="my_constraint", use_registry=True, tier=1)
def my_protected_function():
    pass
```

**Option C: Physical action type**
```python
# In packages/kagami_smarthome/safety.py

class PhysicalActionType(str, Enum):
    # ... existing types ...
    MY_ACTION = "my_action"

def _check_rule_based_safety(context: SafetyContext) -> SafetyResult:
    # ... existing rules ...
    elif context.action_type == PhysicalActionType.MY_ACTION:
        h_x = 0.7
        warnings.append("Custom warning message")
```

---

## Emergency Halt

For immediate safety override:

```python
from kagami.core.safety.cbf_integration import (
    emergency_halt,
    reset_emergency_halt,
    is_emergency_halt_active
)

# Block ALL actions (h(x) = -infinity)
emergency_halt()

# Check status
if is_emergency_halt_active():
    print("Emergency halt active - all operations blocked")

# Resume normal operation
reset_emergency_halt()
```

---

## Concurrent Safety (Race Condition Protection)

When multiple colonies execute in parallel, use atomic checks:

```python
from kagami.core.safety.cbf_integration import check_cbf_for_operation_atomic

# Atomic lock prevents race conditions where:
# - Colony A checks h(x) = 0.05, passes
# - Colony B checks h(x) = 0.05, passes
# - Both execute, combined effect: h(x) = -0.1 (VIOLATION!)

result = await check_cbf_for_operation_atomic(
    operation="parallel_colony_execution",
    action="multi_agent_task",
    metadata={"autonomous": True}
)
```

**Safety Buffer:** Operations too close to boundary (h(x) < 0.1) are rejected in atomic mode to account for concurrent effects.

---

## Monitoring (Non-Blocking)

For observability without enforcement:

```python
from kagami.core.safety.cbf_decorators import monitor_cbf

@monitor_cbf(barrier_name="memory", alert_threshold=0.2)
def allocate(self, size: int):
    # Always executes, but logs warning if h(x) < 0.2
    self.memory += size
```

---

## Testing

```bash
# Smart testing - only affected tests
make test-smart

# Or full tier runs:
make test-tier-1

# Type checking
make typecheck

# Lint
make lint

# Property-based tests
pytest tests/property/test_cbf_properties.py

# Safety integration tests
pytest tests/integration/test_safety_systems_comprehensive.py
```

---

## Security Checklist

- [ ] All inputs validated before reaching CBF
- [ ] No SQL injection (use parameterized queries)
- [ ] No command injection (no shell=True with user input)
- [ ] Auth required for protected endpoints
- [ ] Secrets not hardcoded (use Keychain)
- [ ] CBF checks cannot be bypassed (fail-closed)
- [ ] Emergency halt accessible to owner

---

## Don't Do This

```python
# NEVER bypass CBF
result.safe = True  # DO NOT MODIFY

# NEVER use heuristics for safety classification
if "dangerous" in user_input:  # NO! Use LLM classifier
    return unsafe

# NEVER use eval/exec with user input
eval(user_input)
exec(user_input)
subprocess.run(cmd, shell=True)  # with user input

# NEVER disable barriers in production
registry.disable("organism.memory")  # DANGEROUS
```

---

## References

- Ames et al. (2019): "Control Barrier Functions: Theory and Applications"
- Thom (1972): "Structural Stability and Morphogenesis"
- Sun et al.: "Safety Assessment of Chinese Large Language Models" (Safe RLHF)
- BarrierNet: Neural network barrier functions
