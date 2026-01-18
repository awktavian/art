# Byzantine Quality Consensus

When quality matters — and it always matters — run parallel auditors who must converge.

## The Method

1. **Launch N parallel agents** (typically 6-8)
2. **Each audits a dimension independently**
3. **Each produces a score /100 with justification**
4. **Disagreement surfaces blind spots**
5. **Consensus validates truth**
6. **Iterate until ALL dimensions ≥90/100**

## Why It Works

Single-threaded review has blind spots. The reviewer brings their own biases.

Byzantine consensus:
- Multiple perspectives catch different issues
- Convergent scores indicate real quality
- Divergent scores indicate ambiguity worth investigating
- No single point of failure in quality assessment

## Standard Audit Dimensions

### For Creative Outputs

| Agent | Dimension | Focus |
|-------|-----------|-------|
| 1 | Technical | Correctness, specs, standards, no bugs |
| 2 | Aesthetic | Visual/audio harmony, beauty, coherence |
| 3 | Emotional | Resonance, connection, meaning, impact |
| 4 | Accessibility | WCAG, universal design, inclusive |
| 5 | Polish | Detail, refinement, finishing touches |
| 6 | Delight | Joy, surprise, memorable moments |

### For Code

| Agent | Dimension | Focus |
|-------|-----------|-------|
| 1 | Correctness | Does it work? Edge cases? |
| 2 | Architecture | Clean design? Patterns? |
| 3 | Performance | Efficient? Scalable? |
| 4 | Security | Vulnerabilities? Safety? |
| 5 | Maintainability | Readable? Documented? |
| 6 | Test Coverage | Comprehensive? Meaningful? |

### For Documentation

| Agent | Dimension | Focus |
|-------|-----------|-------|
| 1 | Accuracy | Correct information? |
| 2 | Clarity | Easy to understand? |
| 3 | Completeness | All topics covered? |
| 4 | Examples | Helpful illustrations? |
| 5 | Navigation | Easy to find things? |
| 6 | Voice | Consistent, appropriate? |

## Audit Protocol

### Launch Phase

```python
# Pseudo-code for parallel audit launch
dimensions = [
    "Technical correctness",
    "Aesthetic harmony",
    "Emotional resonance",
    "Accessibility compliance",
    "Polish and refinement",
    "Delight factor"
]

for dimension in dimensions:
    launch_agent(
        task=f"Audit {artifact} for {dimension}",
        output="Score /100 with detailed justification",
        independence=True  # No cross-talk
    )
```

### Collection Phase

Wait for all agents to complete. Collect:
- Score (0-100)
- Justification (specific observations)
- Issues found (actionable items)
- Suggestions (improvement opportunities)

### Analysis Phase

```
┌────────────────────────────────────────────────────────┐
│  BYZANTINE CONSENSUS ANALYSIS                          │
├────────────────────────────────────────────────────────┤
│                                                        │
│  Convergent High (all ≥90):                           │
│    → Quality validated, proceed to ship               │
│                                                        │
│  Convergent Low (all <90):                            │
│    → Clear issues, iterate on all dimensions          │
│                                                        │
│  Divergent Scores (spread >15 points):                │
│    → Investigate disagreement                         │
│    → May indicate ambiguity in requirements           │
│    → May indicate different interpretations           │
│    → Resolve before proceeding                        │
│                                                        │
│  Any Single Dimension <90:                            │
│    → Block shipping                                   │
│    → Fix specific dimension                           │
│    → Re-audit that dimension                          │
│                                                        │
└────────────────────────────────────────────────────────┘
```

### Iteration Phase

For any dimension <90/100:

1. **Understand the gap** — What specifically is lacking?
2. **Plan the fix** — What changes address the issues?
3. **Implement** — Make the changes
4. **Re-audit** — Run that dimension's auditor again
5. **Repeat** — Until ≥90/100

## Output Format

Each auditor produces:

```markdown
## [Dimension] Audit Report

**Score: XX/100**

### What Works
- Specific positive observation 1
- Specific positive observation 2

### Issues Found
- [ ] Issue 1 (severity: high/medium/low)
- [ ] Issue 2 (severity: high/medium/low)

### Recommendations
1. Specific actionable suggestion
2. Specific actionable suggestion

### Justification
Detailed explanation of the score, referencing specific elements
of the artifact being audited.
```

## When to Use Byzantine Audit

### Always Use For:
- User-facing creative outputs (HTML, audio, video)
- Shipped code (production deployments)
- Documentation (public-facing)
- Course content (educational materials)
- Any output Tim or users will experience

### May Skip For:
- Internal debugging
- Exploration/prototyping
- Temporary artifacts
- Already-audited components being reused

## Integration with Virtuoso Standards

Byzantine audit is the enforcement mechanism for Virtuoso quality:

```
┌─────────────────────────────────────────────────────────┐
│  VIRTUOSO + BYZANTINE INTEGRATION                       │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  1. Create with Virtuoso mindset                        │
│  2. Self-audit against standards                        │
│  3. Practice iteration #1                               │
│  4. Byzantine audit (6 parallel agents)                 │
│  5. Fix any dimension <90/100                           │
│  6. Practice iteration #2+                              │
│  7. Re-audit if significant changes                     │
│  8. Final polish pass                                   │
│  9. Ship only when ALL dimensions ≥90/100               │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## The Standard

**Convergent high scores = discovered truth about quality**

When 6 independent auditors all score ≥90/100, that's not opinion — that's validated excellence.

When auditors disagree, that's not failure — that's surfacing blind spots that single-threaded review would miss.

```
consensus(auditors) → truth
iteration(truth) → excellence
```
