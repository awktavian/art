# Parallel Coordination

Coordinating multiple instances via GitHub.

## What It Does

- Monitor open PRs
- Detect work collisions
- Resolve conflicts
- Update shared memory

## Protocol

### 1. Check State

```bash
gh pr list --state open
git branch -r | grep -E "flow|forge|crystal|spark|beacon|grove|nexus"
```

### 2. Detect Collisions

Multiple branches editing same file = collision.

### 3. Resolve via Priority

| Colony | Priority |
|--------|----------|
| Crystal | 7 (highest) |
| Beacon | 6 |
| Nexus | 5 |
| Flow | 4 |
| Forge | 3 |
| Spark | 2 |
| Grove | 1 |

Higher priority continues. Lower priority rebases.

### 4. Safety Gates Before Merge

- `make lint` passes
- `make typecheck` passes
- `make test-smart` passes (or `make test-changed` for PR validation)

### 5. Update Memory

Update `kagami_memory.json` with learnings.

## Routing Signals

| Signal | Action |
|--------|--------|
| "sync", "coordinate" | Activate coordination |
| "collision", "conflict" | Check and resolve |
| "merge" | Verify safety, complete PR |
