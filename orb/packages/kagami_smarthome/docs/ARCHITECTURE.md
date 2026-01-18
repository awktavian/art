# SmartHome Architecture

## Overview

The `kagami_smarthome` package provides unified smart home control with a room-centric architecture. It integrates 35+ devices across multiple ecosystems into a single coherent API.

## Core Principles

1. **Room-Centric**: Each room is a first-class citizen with its own state, preferences, and capabilities
2. **Service-Oriented**: Domain logic is decomposed into specialized services
3. **Safety-First**: All physical actions pass through CBF (Control Barrier Function) validation
4. **Resilient**: Automatic failover, reconnection, and graceful degradation

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     SmartHomeController                          │
│                     (Slim Facade ~500 LOC)                       │
├─────────────────────────────────────────────────────────────────┤
│  Security Layer: Validation │ Rate Limiter │ Audit Trail        │
├─────────────────────────────────────────────────────────────────┤
│                    14 Domain Services                            │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐               │
│  │DeviceService│ │ AVService   │ │ClimateService│              │
│  └─────────────┘ └─────────────┘ └─────────────┘               │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐               │
│  │SecuritySvc  │ │ TeslaService│ │ SceneService │              │
│  └─────────────┘ └─────────────┘ └─────────────┘               │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐               │
│  │ RoomService │ │PresenceService│ │AutomationSvc│             │
│  └─────────────┘ └─────────────┘ └─────────────┘               │
│  + OeloService, WorkshopService, HealthService, FindMyService   │
│  + VisitorService                                                │
├─────────────────────────────────────────────────────────────────┤
│                    Infrastructure Managers                       │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐   │
│  │IntegrationManager│ │  StateManager   │ │ FailoverManager │   │
│  └─────────────────┘ └─────────────────┘ └─────────────────┘   │
│  ┌─────────────────┐ ┌─────────────────┐                        │
│  │ IntegrationPool │ │PerformanceMonitor│                       │
│  └─────────────────┘ └─────────────────┘                        │
├─────────────────────────────────────────────────────────────────┤
│                    35+ Integrations                              │
│  Control4 │ UniFi │ Tesla │ Denon │ Eight Sleep │ August │ ... │
└─────────────────────────────────────────────────────────────────┘
```

## Package Structure

```
kagami_smarthome/
├── controller.py          # Slim facade (unified entry point)
├── types.py               # Core data types (HomeState, etc.)
├── safety.py              # CBF safety integration
│
├── services/              # 14 Domain Services
│   ├── device_service.py  # Lights, shades, fireplace, TV mount
│   ├── av_service.py      # Audio, TV, home theater
│   ├── climate_service.py # HVAC, bed temperature
│   ├── security_service.py# Locks, cameras, alarms
│   └── ...
│
├── integrations/          # Device integrations
│   ├── control4.py        # Control4 Director API
│   ├── unifi.py           # UniFi Protect + Network
│   ├── tesla.py           # Tesla Fleet API
│   └── ...
│
├── core/                  # Infrastructure
│   ├── integration_manager.py
│   └── state_manager.py
│
├── presence.py            # Presence engine
├── presence_patterns.py   # Pattern learning
├── presence_inference.py  # Intent prediction
│
├── validation.py          # Input validation (Pydantic)
├── rate_limiter.py        # API rate limiting
├── audit.py               # Action audit trail
│
└── tests/                 # Test suite
```

## Data Flow

### Command Flow (User → Device)

```
1. User calls controller.set_lights(50, rooms=["Living Room"])
2. Validation layer validates input (LightCommand)
3. Rate limiter checks/waits for capacity
4. Audit trail starts tracking action
5. DeviceService.set_lights() is called
6. Control4Integration sends command
7. Audit trail records success/failure
8. Result returned to user
```

### Event Flow (Device → User)

```
1. UniFi WebSocket receives motion event
2. PresenceEngine.process_event() updates state
3. PatternLearner records observation
4. StateManager updates HomeState
5. Callbacks notify subscribers
6. Recommendations generated
```

## Key Components

### SmartHomeController

The slim facade providing the unified API:

```python
controller = SmartHomeController(config)
await controller.initialize()

# Room-centric operations
await controller.set_lights(50, rooms=["Living Room"])
await controller.close_shades(rooms=["Primary Bed"])
await controller.set_room_temp("Office", 72)

# Scene operations
await controller.movie_mode()
await controller.goodnight()

# State queries
state = controller.get_state()
health = controller.get_integration_health()
```

### Domain Services

Each service owns a specific domain:

| Service | Responsibility | Integrations |
|---------|---------------|--------------|
| DeviceService | Lights, shades, fireplace, TV mount | Control4 |
| AVService | Audio zones, TV, home theater | Denon, LG TV, Samsung TV, Spotify |
| ClimateService | HVAC, bed temperature | Mitsubishi, Eight Sleep |
| SecurityService | Locks, cameras, alarms | August, UniFi, Envisalink |
| TeslaService | Vehicle presence, charging | Tesla Fleet API |
| SceneService | Scene activation, routines | All |
| RoomService | Room-centric operations | Control4 |
| PresenceService | Location, activity, intent | UniFi, DSC, Find My |

### Presence Engine

Combines sensor inputs to infer:
- WHERE you are (per-room tracking)
- WHAT you're doing (activity context)
- WHAT you'll do next (intent prediction)
- Learned preferences

Components:
- `PresenceEngine` - Main inference engine
- `PatternLearner` - Daily pattern learning (EMA-based)
- `IntentPredictor` - Multi-signal fusion

### Safety Layer (CBF)

All critical physical actions pass through CBF:

```python
# safety.py
async def check_physical_safety(context: SafetyContext) -> SafetyResult:
    if _check_cbf_available():
        return _check_cbf_safety(context)
    return _check_rule_based_safety(context)
```

Protected actions:
- Fireplace on/off (with auto-off timer)
- Lock/unlock
- TV mount movement
- Extreme HVAC settings

### Security Infrastructure

Three layers of security:

1. **Validation** (`validation.py`): Pydantic models for all inputs
2. **Rate Limiting** (`rate_limiter.py`): Per-integration limits
3. **Audit Trail** (`audit.py`): Full action logging

## Integration Points

### Adding a New Integration

1. Create integration file in `integrations/`
2. Implement standard interface:
   ```python
   class NewIntegration:
       async def connect(self) -> bool
       async def disconnect(self) -> None
       def is_connected(self) -> bool
       async def health_check(self) -> HealthStatus
   ```
3. Register in `IntegrationManager`
4. Create service methods in appropriate domain service

### Adding a New Service

1. Create service file in `services/`
2. Implement service class with injected dependencies
3. Add to `services/__init__.py` exports
4. Wire in `SmartHomeController.__init__`

## Configuration

```python
from kagami_smarthome import SmartHomeConfig

config = SmartHomeConfig(
    auto_discover=True,           # Use UniFi for device discovery
    known_devices=["AA:BB:CC:DD:EE:FF"],  # Owner device MACs
    away_timeout_minutes=30,      # Time until marked away
    sleep_start_hour=22,          # Bedtime hour
    sleep_end_hour=6,             # Wake hour
)
```

## Performance

- **Boot time**: ~3s (parallel initialization)
- **Command latency**: <100ms (local integrations)
- **WebSocket events**: <50ms latency
- **Pattern learning**: EMA with 0.1 learning rate

## Testing

```bash
# Run all tests
pytest packages/kagami_smarthome/tests/

# Run specific test file
pytest packages/kagami_smarthome/tests/test_validation.py

# Run with coverage
pytest --cov=kagami_smarthome packages/kagami_smarthome/tests/
```

## Error Handling

All operations use structured error handling:

```python
try:
    await controller.set_lights(50, rooms=["Living Room"])
except ValidationError as e:
    # Invalid input
except ConnectionError as e:
    # Integration unavailable
except SafetyError as e:
    # CBF rejected action
```

## Monitoring

```python
# Get integration health
health = controller.get_integration_health()
# Returns: {"control4": "healthy", "unifi": "healthy", ...}

# Get performance stats
stats = controller.get_performance_summary()
# Returns: {"avg_latency_ms": 45, "success_rate": 0.99, ...}

# Get audit trail
from kagami_smarthome import get_audit_trail
trail = get_audit_trail()
failures = trail.get_failures(count=10)
```
