# Scripts — Repeatable Operations

**All scripts are designed to be repeatable and idempotent.**

No one-offs. No manual intervention. Every process can be automated.

---

## Directory Structure

```
scripts/
├── ci/          # CI/CD automation (GitHub Actions)
├── core/        # Core system operations
├── db/          # Database management
├── deploy/      # Deployment and infrastructure
├── hooks/       # Git hooks
├── ops/         # Operational procedures
├── quality/     # Quality scoring and metrics
├── security/    # Security management
└── training/    # TPU training infrastructure
```

---

## Categories

### CI/CD (`scripts/ci/`)

| Script | Purpose | When to Run |
|--------|---------|-------------|
| `aggregate_security_findings.py` | Aggregate security scan results | CI pipeline |
| `check_bare_except.py` | Detect bare except clauses | Pre-commit |
| `check_file_length.py` | Enforce file length limits | Pre-commit |
| `continuous_improvement_daemon.py` | Auto-fix CI failures | Background |
| `detect_duplicates.py` | Find duplicate code | Weekly audit |
| `enforce_coverage_threshold.py` | Block PRs below coverage | CI pipeline |
| `quality_dashboard.py` | Generate quality metrics | CI pipeline |
| `type_coverage_ratchet.py` | Ensure type coverage grows | CI pipeline |
| `type_safety_dashboard.py` | Type safety metrics | CI pipeline |

### Core Operations (`scripts/core/`)

| Script | Purpose | When to Run |
|--------|---------|-------------|
| `ensure_full_operation.py` | Verify all systems operational | On boot |
| `metrics_lint.py` | Lint metrics definitions | Pre-commit |
| `self_diagnostic.py` | Run self-diagnostics | Troubleshooting |

### Database (`scripts/db/`)

| Script | Purpose | When to Run |
|--------|---------|-------------|
| `backup.py` | Backup database | Daily cron |
| `migrate.py` | Run migrations | Before deploy |
| `restore.py` | Restore from backup | Recovery |
| `rollback.py` | Rollback migration | Recovery |
| `seed.py` | Seed test data | Dev setup |
| `verify.py` | Verify database health | Post-deploy |

### Deployment (`scripts/deploy/`)

| Script | Purpose | When to Run |
|--------|---------|-------------|
| `agent_coordinator.py` | Coordinate multi-agent deployment | Deploy |
| `analyze_topology.py` | Analyze service topology | Planning |
| `check_complexity_budget.py` | Enforce complexity limits | CI |
| `check_metrics_health.py` | Verify metrics health | Post-deploy |
| `check_safety_bypass.py` | Detect safety bypasses | CI |
| `configure_cached_models.py` | Set up model cache | Deploy |
| `dashboard_server.py` | Run metrics dashboard | Monitoring |
| `download_hf_models.py` | Download HuggingFace models | Initial setup |
| `enforce_layering.py` | Enforce architectural layers | CI |
| `etcd_backup.py` | Backup etcd cluster | Daily cron |
| `etcd_restore.py` | Restore etcd cluster | Recovery |
| `monitor_convergence.sh` | Monitor consensus convergence | Ops |
| `pre-start-checks.sh` | Pre-start health checks | Boot |
| `report_type_ignores.py` | Report type ignores | Weekly |
| `reset_operational_state.sh` | Reset to clean state | Recovery |
| `validate_batch_size.py` | Validate batch configurations | Deploy |
| `validate_staging.sh` | Validate staging environment | Pre-prod |
| `verify_db.py` | Verify database connection | Deploy |
| `verify_hardening.py` | Verify security hardening | Deploy |
| `verify_redis.py` | Verify Redis connection | Deploy |
| `verify_stampede_protection.py` | Verify cache stampede protection | Deploy |
| `vulture_whitelist.py` | Dead code whitelist | CI |
| `wait-for-healthy.sh` | Wait for services healthy | Deploy |
| `METRICS.sh` | Collect deploy metrics | Deploy |

### Git Hooks (`scripts/hooks/`)

| Script | Purpose | When to Run |
|--------|---------|-------------|
| `install-hooks.sh` | Install git hooks | Dev setup |
| `sync-prompts.py` | Sync colony prompts | Pre-commit |

### Operations (`scripts/ops/`)

| Script | Purpose | When to Run |
|--------|---------|-------------|
| `autonomous_monitor.sh` | Autonomous health monitor | Background |
| `train.sh` | Launch training | Manual |
| `validate_secrets.py` | Validate all secrets present | Deploy |

### Quality (`scripts/quality/`)

| Script | Purpose | When to Run |
|--------|---------|-------------|
| `score_commit.py` | Score commit quality | Pre-commit |

### Security (`scripts/security/`)

| Script | Purpose | When to Run |
|--------|---------|-------------|
| `audit_secrets.py` | Audit secret usage | Weekly |
| `generate_cache_secret.py` | Generate cache secrets | Initial setup |
| `generate_secrets.py` | Generate all secrets | Initial setup |
| `migrate_all_secrets.py` | Migrate secrets to keychain | Migration |
| `rotate_secrets.py` | Rotate secrets | Quarterly |
| `setup_secrets.py` | Set up secret infrastructure | Initial setup |
| `verify_pickle_fix.py` | Verify pickle security | CI |

### Training (`scripts/training/`)

| Script | Purpose | When to Run |
|--------|---------|-------------|
| `launch_tpu_training.sh` | Launch TPU training job | Manual |
| `profile_tpu.py` | Profile TPU performance | Optimization |
| `setup_gcs_buckets.py` | Set up GCS infrastructure | Initial setup |

---

## Root Scripts

| Script | Purpose | When to Run |
|--------|---------|-------------|
| `kagami_api_launcher.py` | Launch Kagami API server | Boot |
| `kagami_status.py` | Check system status | Troubleshooting |
| `smart_home_daemon.py` | Smart home background service | Boot |
| `start-kagami.sh` | Main startup script | Boot |
| `verify_composio.py` | Verify Composio integration | Deploy |
| `verify_integrations.py` | Verify all integrations | Deploy |
| `verify_precommit_setup.sh` | Verify pre-commit hooks | Dev setup |

---

## Principles

1. **Idempotent** — Running twice has same effect as once
2. **Repeatable** — Same inputs produce same outputs
3. **Logged** — All operations logged for audit
4. **Fail-safe** — Failures don't corrupt state
5. **Documented** — Each script has usage in docstring

---

## Adding New Scripts

1. Place in appropriate category folder
2. Add docstring with usage
3. Ensure idempotency
4. Add to this README
5. No one-offs!

---

## Deleted One-Offs (Historical)

The following categories were removed as one-offs:
- `scripts/demo/` — Demo scripts
- `scripts/research/` — Research experiments
- `scripts/swarm_coordination/` — Coordination experiments
- `scripts/testing/` — Moved to `tests/`
- `scripts/maintenance/` — Merged into appropriate categories
- `scripts/refactor/` — Completed refactors
- `scripts/audit/` — Merged into CI
- `scripts/validation/` — Merged into deploy

**Before: 238 scripts | After: 67 scripts (72% reduction)**
