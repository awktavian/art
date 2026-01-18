# Byzantine Consensus for Quality Assurance

When quality matters, run parallel auditors who must converge.

---

## The Problem

Single-threaded review has blind spots. The reviewer brings their own biases, expertise, and fatigue. One person can't catch everything.

**Traditional Review:**
```
Code → Single Reviewer → "LGTM" → Ship
                 ↓
        (missed edge cases)
```

**Byzantine Consensus:**
```
           ┌→ Auditor 1 (Narrative) → 92/100 ─┐
           │                                    │
Code/Art → ├→ Auditor 2 (Visual)    → 88/100 ──┼→ Converge → Ship
           │                                    │
           ├→ Auditor 3 (Technical) → 95/100 ──┤
           │                                    │
           ├→ Auditor 4 (Accessibility) → 71/100 ─┘ (REMEDIATE!)
           │
           └→ Auditor N...
```

---

## The Method

### 1. Diagonalize

Break the artifact into N independent dimensions. Each dimension gets its own auditor.

**For Tool Time University:**
| Auditor | Dimension | Focus |
|---------|-----------|-------|
| 1 | Narrative Arc | Tim/Al voice, story structure |
| 2 | Visual/CSS | Contrast, spacing, responsive |
| 3 | Technical Accuracy | Code correctness, API alignment |
| 4 | Accessibility | WCAG, keyboard nav, screen readers |
| 5 | Gamification | HED coherence, badge logic |
| 6 | Canvas Compatibility | QTI format, export structure |

### 2. Launch Parallel

All auditors run simultaneously. In Claude Code:

```python
# Launch 6 parallel audit agents in SINGLE message
Task(subagent_type="Explore",
     prompt="Audit narrative arc: Tim/Al voice authenticity, story structure, humor landing...",
     description="Audit narrative arc")
Task(subagent_type="Explore",
     prompt="Audit visual CSS: contrast ratios, spacing grid, responsive breakpoints...",
     description="Audit visual CSS")
# ... 4 more in same message
```

**Key**: All Task calls in ONE message enables true parallelism.

### 3. Independent Scoring

Each auditor produces a score /100 with specific findings:

```
Narrative Audit:
- Tim voice authenticity: 94/100
- Al counterbalance: 91/100
- Wilson wisdom delivery: 88/100
- Story arc completion: 92/100
- OVERALL: 91/100

Findings:
- mod01-assignment missing Tim grunt (line 47)
- final-project could use Answer-O-Matic humor
```

### 4. Convergent Findings

When multiple auditors flag the same issue, it's validated truth:

| Finding | Auditors Who Found It | Confidence |
|---------|----------------------|------------|
| mod01 missing grunt | Narrative, Voice | HIGH |
| Contrast too low | Visual, Accessibility | HIGH |
| Modal timing arbitrary | Visual | MEDIUM |

### 5. Threshold Gate

| Score Range | Action |
|-------------|--------|
| 95-100 | Ship |
| 90-94 | Ship with notes |
| 80-89 | Minor remediation |
| 70-79 | Significant remediation |
| <70 | Major rework |

**Byzantine rule**: If ANY dimension scores <70, the whole artifact fails. Quality is multiplicative.

---

## Why "Byzantine"?

The name comes from the Byzantine Generals Problem in distributed systems. Generals must agree on a battle plan, but some may be traitors (unreliable).

**Solution**: If 2/3+ of generals agree, the decision is valid even with traitors.

**Applied to quality**:
- Each auditor is a "general"
- Their independent findings are "votes"
- Convergent findings (2+ auditors agree) are "consensus"
- Divergent findings (only 1 auditor) need investigation

---

## Implementation

### Claude Code Pattern

```python
# 1. Define dimensions
dimensions = [
    ("narrative", "Audit narrative: Tim/Al voice, story arc, humor landing"),
    ("visual", "Audit CSS: contrast, spacing, responsive, Fibonacci timing"),
    ("technical", "Audit code: correctness, API alignment, error handling"),
    ("accessibility", "Audit a11y: WCAG contrast, keyboard nav, ARIA"),
    ("gamification", "Audit game: HED coherence, badge logic, progression"),
    ("platform", "Audit platform: Canvas QTI format, export structure"),
]

# 2. Launch all in parallel (SINGLE message with multiple Task calls)
for name, prompt in dimensions:
    Task(
        subagent_type="Explore",
        prompt=prompt,
        description=f"Audit {name}"
    )

# 3. Collect results (wait for all to complete)
results = [TaskOutput(task_id=id) for id in task_ids]

# 4. Synthesize
for result in results:
    if result.score < 70:
        print(f"FAIL: {result.dimension} at {result.score}/100")
        # Generate remediation tasks

# 5. Execute remediation in priority order
```

### Memory Persistence

Store audit state in Memory MCP:

```python
mcp__memory__create_entities(entities=[
    {
        "name": "TTU_Audit_Jan03_2026",
        "entityType": "AuditSession",
        "observations": [
            "Started: 2026-01-03T10:00:00Z",
            "Dimensions: 6",
            "Status: IN_PROGRESS"
        ]
    },
    {
        "name": "TTU_Narrative_Audit",
        "entityType": "AuditDimension",
        "observations": [
            "Score: 91/100",
            "Finding: mod01 missing grunt",
            "Finding: final-project needs Answer-O-Matic"
        ]
    }
])
```

---

## When to Use It

**YES - Use Byzantine Consensus:**
- Course/curriculum before launch
- App UI before major release
- Documentation for public APIs
- Marketing materials
- Anything user-facing where quality matters

**NO - Skip Byzantine Consensus:**
- Quick fixes (single dimension affected)
- Internal tooling (low stakes)
- Exploratory prototypes
- Time-critical hotfixes

---

## Anti-Patterns

| Don't | Do |
|-------|-----|
| Use one reviewer for complex work | Parallelize across dimensions |
| Average the scores | Gate on lowest score |
| Ignore minority findings | Investigate divergence |
| Run audits sequentially | Launch all in ONE message |
| Trust single strong score | Require ALL dimensions pass |

---

## The Philosophy

Byzantine consensus isn't about distrust — it's about coverage.

No single perspective catches everything. A visual expert misses accessibility. A narrative expert misses technical bugs. An accessibility expert misses story flow.

By running parallel auditors with convergent voting, we:
1. **Find more issues** (coverage)
2. **Validate real issues** (consensus)
3. **Reduce false positives** (divergence investigation)
4. **Ship with confidence** (all dimensions pass)

---

*When 6 auditors converge on the same finding, that's not opinion — that's discovered knowledge.*

鏡
