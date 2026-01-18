# Database Migrations

This directory contains database migrations for Kagami.

## Migration Format

**Standard**: Alembic (Python-based migrations)

Alembic is the preferred migration format. New migrations should be created using:

```bash
alembic revision --autogenerate -m "description"
```

## Legacy SQL Migrations

Some older migrations are in raw SQL format (`.sql` files). These are applied manually
and should be converted to Alembic format over time.

**Legacy SQL files** (to be converted):
- `004_intelligence_indexes.sql`
- `202501_learning_state_persistence.sql`
- `20251027_add_receipt_indexes.sql`
- `20251116_add_multi_tenancy.sql`
- `20251215_webhook_idempotency_constraint.sql`
- `20251216_correlation_id_uniqueness_constraint.sql`
- `20251219_add_parent_receipt_id.sql`
- `20251220_add_performance_indexes.sql`
- `20251221_critical_fixes.sql`
- `20251222_fix_parent_receipt_id_type.sql`
- `20260101_households_multiuser.sql`

**Alembic migrations** (current format):
- `20251228_add_colony_and_training_tables.py`
- `add_privacy_tables.py`

## Running Migrations

### Alembic (Recommended)

```bash
# Apply all pending migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# Check current revision
alembic current
```

### Legacy SQL (Manual)

```bash
# Apply a SQL migration
psql -d kagami -f migrations/versions/filename.sql
```

## Environment Variables

- `DATABASE_URL`: PostgreSQL/CockroachDB connection string
- `ALEMBIC_CONFIG`: Path to alembic.ini (default: ./alembic.ini)

## Creating New Migrations

Always use Alembic for new migrations:

```bash
# Auto-generate from model changes
alembic revision --autogenerate -m "add_new_table"

# Empty migration for manual SQL
alembic revision -m "custom_migration"
```

## Production Notes

1. Always backup the database before running migrations
2. Test migrations in staging first
3. Use transactions for data migrations
4. Document rollback procedures for each migration
