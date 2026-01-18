# Quality Skill

Testing and verification.

## Smart Testing (RECOMMENDED)

```bash
# During development - only test what changed
make test-smart

# Before commit - test staged changes
make test-smart-cached

# Before push - test vs main branch
make test-changed
```

## Quick Check

```bash
make lint && make typecheck && make test-smart
```

## Commands

| Command | Time | Purpose |
|---------|------|---------|
| `make test-smart` | ~30s | Only affected tests |
| `make test-smart-cached` | ~30s | Staged changes only |
| `make test-changed` | ~1-2 min | Changes vs main |
| `make test-tier-1` | 2 min | All unit tests |
| `make test-tier-2` | 5 min | Integration |
| `make lint` | Quick | Ruff |
| `make typecheck` | Quick | mypy |

## Preview (Dry Run)

```bash
make test-smart-preview       # What would run?
make test-smart-preview-cached
make test-smart-preview-main
```

## pytest-testmon

Deep dependency tracking (imports/calls):

```bash
make testmon-setup    # Install once
make test-testmon     # Selective runs
```

## Common Fixes

| Issue | Fix |
|-------|-----|
| Unused variable | Remove or prefix `_` |
| Missing return type | Add `-> None` |
| Unused import | Delete line |
