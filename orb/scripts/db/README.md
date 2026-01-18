# Database Management Scripts

This directory contains database management utilities for Kagami.

## Prerequisites

1. Set `DATABASE_URL` environment variable:
   ```bash
   export DATABASE_URL="postgresql://user:password@localhost:26257/kagami"
   ```

2. Install PostgreSQL client tools (for backup/restore):
   ```bash
   # Ubuntu/Debian
   sudo apt-get install postgresql-client

   # macOS
   brew install postgresql
   ```

## Scripts

### migrate.py - Run Database Migrations

Apply database migrations using Alembic.

```bash
# Migrate to latest version
python scripts/db/migrate.py

# Migrate to specific revision
python scripts/db/migrate.py --target abc123

# Show current database version
python scripts/db/migrate.py --show

# Show migration history
python scripts/db/migrate.py --history
```

### rollback.py - Rollback Migrations

Rollback database migrations.

```bash
# Rollback one migration
python scripts/db/rollback.py

# Rollback 3 migrations
python scripts/db/rollback.py --steps 3

# Rollback to specific revision
python scripts/db/rollback.py --target abc123

# Rollback all migrations (WARNING: destructive)
python scripts/db/rollback.py --all
```

### seed.py - Seed Test Data

Populate database with test data.

```bash
# Seed development data
python scripts/db/seed.py --env dev

# Seed test data
python scripts/db/seed.py --env test
```

Creates sample data including:
- Test users (admin, testuser)
- Colony states (7 colonies)
- Training runs (completed and in-progress)
- Receipts (PLAN/EXECUTE/VERIFY triplets)
- Plans and goals

### backup.py - Backup Database

Create database backups using pg_dump.

```bash
# Backup to default location (backups/kagami_TIMESTAMP.sql)
python scripts/db/backup.py

# Backup to specific file
python scripts/db/backup.py --output /path/to/backup.sql

# Backup with custom format (better compression)
python scripts/db/backup.py --format custom --output backup.dump
```

Formats:
- `plain`: SQL text file (default)
- `custom`: PostgreSQL custom format (compressed)
- `tar`: Tar archive

### restore.py - Restore Database

Restore database from backup.

```bash
# Restore from backup
python scripts/db/restore.py backups/kagami_20251228.sql

# Restore with clean (drops existing objects first)
python scripts/db/restore.py backups/kagami_20251228.sql --clean
```

Automatically detects backup format based on file extension.

## Common Workflows

### Initial Setup

```bash
# 1. Run migrations to create tables
python scripts/db/migrate.py

# 2. Seed with test data
python scripts/db/seed.py --env dev
```

### Development Workflow

```bash
# Create a backup before testing
python scripts/db/backup.py --output dev_backup.sql

# Test migrations
python scripts/db/migrate.py

# If something goes wrong, restore
python scripts/db/restore.py dev_backup.sql --clean
```

### Production Deployment

```bash
# 1. Backup production database
python scripts/db/backup.py --format custom --output prod_backup.dump

# 2. Run migrations
python scripts/db/migrate.py

# 3. If issues occur, rollback migrations
python scripts/db/rollback.py --steps 1

# 4. Or restore from backup
python scripts/db/restore.py prod_backup.dump --clean
```

## Creating New Migrations

```bash
# Auto-generate migration from model changes
alembic revision --autogenerate -m "description"

# Create empty migration
alembic revision -m "description"

# Edit the generated file in migrations/versions/
# Then run the migration
python scripts/db/migrate.py
```

## Troubleshooting

### "DATABASE_URL not set"

Ensure the environment variable is set:
```bash
export DATABASE_URL="postgresql://user:password@localhost:26257/kagami"
```

### "pg_dump not found" or "psql not found"

Install PostgreSQL client tools (see Prerequisites).

### Migration fails with "duplicate key"

The database may have existing data that conflicts with the migration. Options:
1. Rollback and reapply: `python scripts/db/rollback.py --steps 1 && python scripts/db/migrate.py`
2. Clean restore: `python scripts/db/restore.py backup.sql --clean`
3. Manually fix the conflict in the database

### "relation already exists"

The migration may have been partially applied. Options:
1. Check current version: `python scripts/db/migrate.py --show`
2. Mark migration as applied: `alembic stamp head`
3. Or restore from backup: `python scripts/db/restore.py backup.sql --clean`

## Database Architecture

Kagami uses:
- **Primary Database**: CockroachDB (PostgreSQL-compatible)
- **ORM**: SQLAlchemy 2.0 (async)
- **Migrations**: Alembic
- **Models**: `/kagami/core/database/models.py`

### Key Tables

- `users` - User authentication
- `receipts` - PLAN/EXECUTE/VERIFY tracking
- `colony_states` - Colony coordination state
- `training_runs` - ML training tracking
- `safety_state_snapshots` - CBF safety tracking
- `world_model_predictions` - World model learning

### Performance Features

- UUID primary keys (no sequential hotspots)
- Hash-sharded indexes (CockroachDB optimization)
- JSONB with GIN indexes (flexible queries)
- Composite indexes (multi-column lookups)
- Foreign key constraints (referential integrity)

## CI/CD Integration

### GitHub Actions Example

```yaml
- name: Run migrations
  env:
    DATABASE_URL: ${{ secrets.DATABASE_URL }}
  run: python scripts/db/migrate.py

- name: Seed test data
  env:
    DATABASE_URL: ${{ secrets.DATABASE_URL }}
  run: python scripts/db/seed.py --env test
```

### Docker Compose

```yaml
services:
  migrate:
    image: kagami:latest
    command: python scripts/db/migrate.py
    environment:
      - DATABASE_URL=${DATABASE_URL}
```

## Safety Best Practices

1. Always backup before migrations in production
2. Test migrations on staging first
3. Use transactions (Alembic does this by default)
4. Keep migrations small and focused
5. Review auto-generated migrations before applying
6. Document breaking changes in migration files
7. Never modify applied migrations (create new ones)

## Support

For issues or questions:
- Check migration logs: `migrations/versions/*.py`
- Review Alembic docs: https://alembic.sqlalchemy.org/
- CockroachDB docs: https://www.cockroachlabs.com/docs/
