# CareOn — OPERATIONS GUIDE

> Updated for Milestone 1: PostgreSQL + PostGIS + Alembic + Redis

---

## 1. Prerequisites

| Tool | Minimum Version | Install |
|------|----------------|---------|
| Python | 3.11+ | `brew install python` |
| PostgreSQL | 17 | `brew install postgresql@17` |
| PostGIS | 3.5+ | `brew install postgis` |
| Redis | 7+ | `brew install redis` |
| Node.js | 18+ | `brew install node` |
| Docker Desktop | 24+ | https://docs.docker.com/desktop/mac/ |

---

## 2. Local Development Setup

### 2.1 Start infrastructure

```bash
brew services start postgresql@17
brew services start redis
```

### 2.2 Create databases

```bash
createdb careon
createdb careon_test

psql -d careon      -c "CREATE EXTENSION IF NOT EXISTS postgis;"
psql -d careon_test -c "CREATE EXTENSION IF NOT EXISTS postgis;"
```

### 2.3 Install backend dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2.4 Configure environment

```bash
cp .env.example .env
# Edit .env — set CAREON_SECRET_KEY (minimum 32 random characters)
```

### 2.5 Run Alembic migrations

```bash
cd backend
alembic upgrade head
```

### 2.6 Start the backend

```bash
cd backend
DATABASE_URL=postgresql+psycopg:///careon \
CAREON_SECRET_KEY=your_secret_key_here \
uvicorn app.main:app --reload --port 8000
```

Demo data is seeded automatically on first startup.

### 2.7 Start the frontend

```bash
cd frontend
npm install
npm start          # → http://localhost:3000
```

---

## 3. Alembic Migration Commands

| Task | Command |
|------|---------|
| Apply all pending migrations | `alembic upgrade head` |
| Downgrade one step | `alembic downgrade -1` |
| Downgrade to base (empty DB) | `alembic downgrade base` |
| Show current revision | `alembic current` |
| Show migration history | `alembic history --verbose` |
| Generate a new migration | `alembic revision --autogenerate -m "describe_change"` |
| Reset and re-apply (destructive!) | `alembic downgrade base && alembic upgrade head` |

> **Important:** Always run `alembic upgrade head` before starting the backend in production.
> Never rely on `Base.metadata.create_all()` for production schema management.

---

## 4. Migrate from SQLite (Legacy) to PostgreSQL

If you have an existing `careon.db` SQLite database:

```bash
cd backend

# Review what will be migrated first (dry-run):
python -m app.migrate_sqlite_to_pg \
  --sqlite-path /path/to/careon.db \
  --pg-url "postgresql+psycopg:///careon" \
  --dry-run

# Perform the actual migration:
python -m app.migrate_sqlite_to_pg \
  --sqlite-path /path/to/careon.db \
  --pg-url "postgresql+psycopg:///careon"
```

The migration tool:
- Preserves all original IDs
- Converts SQLite boolean integers (0/1) to PostgreSQL booleans
- Populates PostGIS `geom` columns from existing `latitude`/`longitude` fields
- Updates PostgreSQL sequences after import
- Validates row counts in all 14 tables before committing

---

## 5. Run Tests

### Unit tests (SQLite — fast, no PostgreSQL required)

```bash
cd backend
CAREON_TESTING=true \
DATABASE_URL=sqlite:///./test_run.db \
PYTHONPATH=. pytest tests/ -q
# M1 integration tests auto-skip; 48 tests pass
```

### Full integration tests (PostgreSQL + Redis required)

```bash
cd backend
CAREON_TESTING=true \
DATABASE_URL=postgresql+psycopg:///careon_test \
REDIS_URL=redis://localhost:6379/0 \
PYTHONPATH=. pytest tests/ -v
# 81 tests pass (48 M0 + 33 M1)
```

### Run only M1 integration tests

```bash
cd backend
CAREON_TESTING=true \
DATABASE_URL=postgresql+psycopg:///careon_test \
REDIS_URL=redis://localhost:6379/0 \
PYTHONPATH=. pytest tests/test_milestone1_postgres.py -v
# 33 tests
```

---

## 6. Docker Compose (Full Stack)

> Requires Docker Desktop to be running.

### First run

```bash
cp .env.example .env
# Edit .env — fill POSTGRES_PASSWORD and CAREON_SECRET_KEY

docker compose up -d

# Run migrations inside the backend container on first run:
docker compose exec backend alembic upgrade head
```

### Subsequent runs

```bash
docker compose up -d        # start all services
docker compose logs -f      # follow logs
docker compose down         # stop (data persisted in volumes)
docker compose down -v      # stop and DELETE all data
```

### Service URLs

| Service | URL |
|---------|-----|
| Backend API | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |
| Frontend | http://localhost:3000 |

---

## 7. Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+psycopg:///careon` | Full database URL |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL |
| `CAREON_ENV` | `development` | `development` / `staging` / `production` |
| `CAREON_SECRET_KEY` | *(required)* | JWT signing secret — min 32 chars |
| `ALLOWED_ORIGINS` | `*` (dev) / `https://careon.org` (prod) | Comma-separated CORS origins |
| `DB_POOL_SIZE` | `10` | SQLAlchemy connection pool size |
| `DB_MAX_OVERFLOW` | `20` | Max extra connections above pool_size |
| `DB_POOL_TIMEOUT` | `30` | Seconds to wait for a connection |
| `DB_POOL_RECYCLE` | `1800` | Recycle connections after N seconds |
| `RATE_LIMIT_AUTH_COUNT` | `10` | Max auth requests per window |
| `RATE_LIMIT_AUTH_WINDOW` | `60` | Auth rate limit window (seconds) |
| `RATE_LIMIT_OTP_COUNT` | `5` | Max OTP attempts per window |
| `RATE_LIMIT_EMERGENCY_COUNT` | `60` | Max incident reports per window |
| `RATE_LIMIT_TRACKING_COUNT` | `60` | Max tracking requests per window |
| `CAREON_TESTING` | — | Set to `true` to disable rate limiting in tests |
| `TRUSTED_PROXIES` | `127.0.0.1,::1` | IPs that may pass X-Forwarded-For |

---

## 8. Spatial Queries

CareOn uses PostGIS for geospatial queries. The `app/spatial.py` module exposes:

```python
from app.spatial import (
    find_resources_within_radius,   # Resources within N metres of a point
    find_incidents_within_radius,   # Incidents within N metres
    find_providers_within_radius,   # External providers within N metres
    distance_between_points,        # Geodesic distance in metres
)

# Example: find ambulances within 10 km of an incident
resources = find_resources_within_radius(
    db, lat=12.3052, lon=76.6552,
    radius_m=10_000,
    status="Available",
    category="Medical Ambulance",
)
```

All functions fall back to Haversine calculation when SQLite is used (unit tests).

---

## 9. Database Backup & Restore

```bash
# Backup
pg_dump careon > careon_backup_$(date +%Y%m%d).sql

# Restore to a fresh database
createdb careon_restore
psql -d careon_restore -c "CREATE EXTENSION IF NOT EXISTS postgis;"
psql -d careon_restore < careon_backup_20260101.sql
```

---

## 10. Git Branches

| Branch | Purpose |
|--------|---------|
| `main` | Stable release baseline |
| `feature/m0-security-hardening` | M0: Security hardening (commit `0afd049`) |
| `feature/m1-postgres-postgis` | M1: PostgreSQL + PostGIS + Alembic + Redis (commit `267cafd`) |

---

## 11. Demo Credentials

| Role | Email | Password |
|------|-------|---------|
| Administrator | `admin@careon.org` | `admin123` |
| Demo User | `user@careon.org` | `user123` |

> **Never** use these credentials in production. Change them before deployment.
