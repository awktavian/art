# Colony Orchestration Skill

Coordinating multiple colonies for complex tasks.

## The Colonies

| Colony | Role | Triggers |
|--------|------|----------|
| Spark | Ideas | brainstorm, ideate |
| Forge | Building | build, implement |
| Flow | Debugging | debug, fix |
| Nexus | Integration | connect, integrate |
| Beacon | Planning | plan, architect |
| Grove | Research | research, explore |
| Crystal | Verification | test, verify |

## Main Workflow

```
PLAN (Beacon, Grove, Spark)
    ↓
EXECUTE (Forge, Nexus, Flow)
    ↓
VERIFY (Crystal)
```

## Common Patterns

### Feature Implementation
```
Spark → ideas
Beacon → plan
Grove → research
Forge → build
Crystal → test
```

### Bug Fix
```
Flow → diagnose
Grove → research
Forge → fix
Crystal → verify
```

### Refactoring
```
Grove → understand current
Beacon → plan new
Forge → implement
Crystal → test each step
```

## Key Files

| File | Purpose |
|------|---------|
| `kagami/orchestration/intent_orchestrator.py` | Intent routing |
| `kagami/core/unified_agents/fano_action_router.py` | Fano routing |
| `kagami/core/unified_agents/` | Colony implementations |
