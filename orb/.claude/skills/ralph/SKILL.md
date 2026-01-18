# Ralph Skill

Parallel agent methodology for complex tasks with persistent state and multi-perspective code review.

*"I'm learnding!" -- Ralph Wiggum*

Iteration wins. Quality emerges from persistence.

---

## Part 1: Workflow

Parallel agent methodology for complex tasks with persistent state.

### Core Loop

```
RESUME -> DIAGONALIZE -> SCORE -> PLAN -> EXECUTE -> VERIFY -> PERSIST
```

### 1. Resume (ALWAYS FIRST)

Every session starts with state recovery:

```bash
# 1. Git state (context resume)
git status
git log --oneline -5

# 2. Memory state (task resume)
mcp__memory__read_graph()
mcp__memory__search_nodes("PENDING")
```

**Why**: Claude Squad edits context. Memory survives context resets.

### 2. Diagonalize

Break complex tasks into parallel sub-tasks. Use Task tool with multiple agents:

```python
# Launch parallel Ralph agents
Task(subagent_type="Explore", prompt="Audit domain X deeply", description="Audit X")
Task(subagent_type="Explore", prompt="Audit domain Y deeply", description="Audit Y")
# ... launch N agents in single message for true parallelism
```

**Naming**: `<Domain>_<Type>` e.g., `Vision_AR_Domain`, `P0_Auth_SmartHome`

### 3. Score

Every audit produces scores /100:

| Score | Meaning |
|-------|---------|
| 90-100 | Excellent |
| 80-89 | Good |
| 70-79 | Acceptable |
| 60-69 | Needs work |
| 50-59 | Poor |
| <50 | Critical |

### 4. Plan

Create prioritized remediation tasks:

| Priority | Criteria |
|----------|----------|
| P0 CRITICAL | Security holes, CBF violations, data exposure |
| P1 HIGH | Session hijacking, missing validation |
| P2 MEDIUM | Missing features, incomplete flows |

### 5. Execute

Work through tasks in priority order. Update Memory status as you go:

```python
# Mark task in progress
mcp__memory__add_observations({
    "observations": [{
        "entityName": "P0_Auth_SmartHome",
        "contents": ["Status: IN_PROGRESS", "Started: 2025-12-31T14:00:00Z"]
    }]
})

# After completion
mcp__memory__add_observations({
    "observations": [{
        "entityName": "P0_Auth_SmartHome",
        "contents": ["Status: COMPLETED", "Completed: 2025-12-31T14:30:00Z"]
    }]
})
```

### 6. Verify

Always verify fixes with smart testing:

```bash
make lint
make typecheck
make test-smart           # Only affected tests
# OR full tier if major changes:
make test-tier-1
```

### 7. Persist

Store everything in Memory MCP - NEVER in CLAUDE.md.

#### Entity Types

| Type | Purpose | Example |
|------|---------|---------|
| AuditSession | Track audit runs | `API_Audit_Dec31_2025` |
| APIDomain | Domain findings | `Vision_AR_Domain` |
| RemediationTask | Fix tasks | `P0_Auth_SmartHome` |
| SecurityComponent | System components | `CBF_Safety_System` |

#### Relation Types

| Relation | Meaning |
|----------|---------|
| audited | Session -> Domain |
| remediates | Task -> Domain/Component |

#### Tagging Convention

All entities must follow naming:
- `<Domain>_Domain` for audit domains
- `P0_<Category>_<Target>` for critical tasks
- `P1_<Category>_<Target>` for high tasks
- `P2_<Category>_<Target>` for medium tasks
- `<Name>_<Type>_<Date>` for sessions

**Why tagging matters**: Easy cleanup. Query by prefix to find/delete related entities.

### Memory Queries

```python
# Get all audit sessions
mcp__memory__search_nodes("Audit")

# Get all pending tasks
mcp__memory__search_nodes("PENDING")

# Get all P0 tasks
mcp__memory__search_nodes("P0_")

# Get specific domain
mcp__memory__search_nodes("Vision_AR")

# Get full graph
mcp__memory__read_graph()
```

### Memory Cleanup

Before starting new audit, clean old data:

```python
# Find entities to delete
old = mcp__memory__search_nodes("Dec30")

# Delete old entities
mcp__memory__delete_entities(entityNames=["API_Audit_Dec30_2025", ...])
```

### Anti-Patterns

| Don't | Do |
|-------|-----|
| Store findings in CLAUDE.md | Use Memory MCP |
| Forget to check git status | Always check first |
| Forget to check Memory | Always check first |
| Create untagged entities | Use naming convention |
| Leave orphaned entities | Clean up after completion |
| Run agents sequentially | Use parallel Task calls |

---

## Part 2: Review

Multi-perspective code review using parallel subagents and iterative improvement.

### The 8-Perspective Framework

Every code artifact is evaluated from 8 lenses:

| Perspective | Focus | Key Questions |
|-------------|-------|---------------|
| **Student** | Learnability | Clear comments? Good progression? Explains "why"? |
| **Professional** | Production-readiness | Error handling? Logging? Config management? |
| **Expert** | Technical depth | Novel patterns? Mathematical rigor? Advanced techniques? |
| **Design** | Architecture | SOLID principles? Separation of concerns? DRY? |
| **Engineer** | Maintainability | Tests? Type hints? Performance? Magic numbers? |
| **Product Manager** | User value | Problem solved? Completeness? Actionable output? |
| **Enthusiast** | Excitement | Cool features? Shareability? Visual appeal? |
| **Security** | Safety | No secrets? Input validation? Safe patterns? |

### Scoring Rubric

| Score | Level | Meaning |
|-------|-------|---------|
| 90-100 | Exceptional | Production-ready, best-in-class |
| 80-89 | Strong | Minor improvements possible |
| 70-79 | Adequate | Gets the job done, lacks polish |
| 60-69 | Weak | Significant gaps, needs work |
| <60 | Poor | Incomplete, broken, or missing |

### Review Workflow

```
1. LAUNCH: Batch files into parallel agents (~10 agents, 3-5 files each)
2. PREP: While waiting, read context (docs, config)
3. COLLECT: Use TaskOutput with block=true when ready
4. DIAGONALIZE: Cross-evaluate perspective x category matrix
5. PLAN: Prioritize by impact (universal > category > file-specific)
6. EXECUTE: Parallel improvement streams
7. VALIDATE: Lint, typecheck, run examples
8. DOCUMENT: Update learnings
```

### Agent Prompt Template

```
Read and analyze these files thoroughly:
1. [file_path_1]
2. [file_path_2]
3. [file_path_3]

For EACH file, score it /100 from these 8 perspectives:
- Student: How easy to learn from? Clear comments? Good progression?
- Professional: Production-ready? Error handling? Logging?
- Expert: Advanced patterns? Novel techniques?
- Design: Architecture? SOLID? Separation of concerns?
- Engineer: Maintainability? Tests? Type hints? Performance?
- Product Manager: User value? Problem solved? Completeness?
- Enthusiast: Excitement? Cool features? Shareability?
- Security: Safe patterns? No secrets? Input validation?

Output format:
FILENAME: [path]
Student: X/100 - [1 line reason]
...
AVERAGE: X/100
TOP 3 IMPROVEMENTS NEEDED:
1. [specific improvement]
2. [specific improvement]
3. [specific improvement]
```

### Diagonalization Matrix

After collecting scores, build a perspective x category matrix:

```
             Student  Prof  Expert  Design  Engineer  PM  Enthus  Security
Flagship      78      68    76      74      62        80  85      75
Technical     80      72    82      78      65        78  75      85
Safety        85      72    80      78      65        75  72      88
Specialized   80      72    75      78      65        80  78      82
```

Identify patterns:
- Which perspective scores consistently lowest? (Often Engineer - tests/types)
- Which category needs most help? (Target those first)
- What systemic fixes apply to ALL files?

### Universal Improvements

These apply to nearly every file:

1. **Error Handling**: Add try/except with specific exceptions
2. **Logging**: Replace print() with logging module
3. **Constants**: Extract magic numbers to named constants
4. **Type Hints**: Complete type annotations (remove `# type: ignore`)
5. **CLI**: Add argparse for --help and configuration

### Parallelism Math

```
Efficiency = (Files x Perspectives) / (Agents x WallClockUnits)

Example: 38 files x 8 perspectives = 304 evaluations
         11 agents x 5 time units = 55 agent-units
         Efficiency = 304/55 = 5.5x evaluation density
```

---

## Part 3: Examples

### Example: API Audit

```python
# 1. Resume
git status
mcp__memory__read_graph()

# 2. Diagonalize - launch 14 parallel agents
Task(subagent_type="Explore", prompt="Audit auth endpoints...", description="Audit auth")
Task(subagent_type="Explore", prompt="Audit home endpoints...", description="Audit home")
# ... 12 more in same message

# 3. Score - each agent returns scores

# 4. Plan - create Memory entities
mcp__memory__create_entities(entities=[
    {"name": "API_Audit_Dec31_2025", "entityType": "AuditSession", "observations": [...]},
    {"name": "Vision_AR_Domain", "entityType": "APIDomain", "observations": ["Score: 46/100", ...]},
    {"name": "P0_Auth_Vision", "entityType": "RemediationTask", "observations": ["Priority: P0", "Status: PENDING", ...]}
])

# 5. Execute - fix issues, update Memory status

# 6. Verify - run tests

# 7. Persist - Memory already updated
```

### Example: Cross-Platform App Improvement

For ecosystem-wide improvements from audit:

```python
# 1. Read master plan
Read(".claude/tasks/RALPH.md")

# 2. Diagonalize by platform - 7 parallel agents
Task(subagent_type="Forge",
     prompt="Implement iOS P0 from RALPH: Login UI, Real API, Siri Shortcuts",
     description="iOS P0 fixes")

Task(subagent_type="Forge",
     prompt="Implement Android P0 from RALPH: Login UI, Real API, Assistant Actions",
     description="Android P0 fixes")

Task(subagent_type="Forge",
     prompt="Implement Watch P0 from RALPH: Login via iPhone, Smart Stack",
     description="Watch P0 fixes")

Task(subagent_type="Forge",
     prompt="Implement Desktop P0: UI modernization, Voice pipeline",
     description="Desktop P0 fixes")

Task(subagent_type="Forge",
     prompt="Implement Hub voice: Wake word, STT, TTS",
     description="Hub P0 fixes")

Task(subagent_type="Forge",
     prompt="Redesign Vision Pro for spatial: 3D depth, real-world anchors",
     description="Vision P0 fixes")

Task(subagent_type="Forge",
     prompt="Implement API parity: Push notifications, Activity log",
     description="API P0 fixes")

# 3. Each agent reports completion to Memory

# 4. Verify cross-platform
# - Feature parity check
# - UI consistency check
# - API coverage check
```

### Platform-Specific Forge Prompts

| Platform | Key Files | Focus Areas |
|----------|-----------|-------------|
| iOS | `ContentView.swift`, `KagamiAPIService.swift` | Siri, Widgets, CarPlay |
| Android | `HomeScreen.kt`, `KagamiApiService.kt` | Assistant, Tiles, Device Controls |
| Watch | `ContentView.swift`, `KagamiAPIService.swift` | Smart Stack, Complications |
| Desktop | `main.rs`, `commands.rs`, `index.html` | UI, Voice, Accessibility |
| Hub | `main.rs`, `voice_pipeline.rs` | Wake word, STT, TTS |
| Vision | `ContentView.swift` | Spatial depth, Anchors |
| API | `routes/home.py` | Push, Activity log |

### Success Metrics Per Platform

| Platform | Metric | Target |
|----------|--------|--------|
| iOS | Siri Shortcuts working | 3+ shortcuts |
| Android | Quick Settings tiles | 4 tiles |
| Watch | Smart Stack visible | Interactive widget |
| Desktop | Keyboard navigation | Full coverage |
| Hub | Wake word response | <500ms |
| Vision | Spatial depth layers | 3 layers |
| API | Push notification delivery | <100ms |

---

## Signals

| Trigger | Action |
|---------|--------|
| "ralph", "review all", "audit" | Full Ralph review |
| "multi-perspective", "evaluate" | Score from 8 lenses |
| "improve examples" | Ralph + improvement loop |
| "workflow", "parallel agents" | Ralph workflow methodology |

## Integration with Other Skills

- **Safety Verification**: h(x) checks during validation
- **Colony Orchestration**: Parallel agent coordination
- **Quality**: Test coverage and type checking
- **Byzantine Quality**: Convergent scoring for validation
