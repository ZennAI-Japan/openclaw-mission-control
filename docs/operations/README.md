# Operations

Runbooks and operational notes for running Mission Control.

## Mission Control operating model

- [Cross-thread governance operating model](./mission-control-governance.md)

### Daily dispatch review (JST)
- Review queue depth by priority (P0/P1/P2)
- Re-score top candidates and confirm dependencies
- Dispatch by policy order and reserve interrupt capacity
- Record assignments/escalations in linked GitHub issues

### Weekly backlog grooming (JST)
- Deduplicate and normalize incoming backlog items
- Reclassify blocked/stale items and split oversized work
- Promote ready work into dispatch queue for next week
- Publish weekly backlog growth/health summary

## Health checks

Backend exposes:

- `/healthz` — liveness
- `/readyz` — readiness

Example:

```bash
curl -f http://localhost:8000/healthz
curl -f http://localhost:8000/readyz
```

## Logs

### Docker Compose

```bash
# tail everything
docker compose -f compose.yml --env-file .env logs -f --tail=200

# tail just backend
docker compose -f compose.yml --env-file .env logs -f --tail=200 backend
```

The backend supports slow-request logging via `REQUEST_LOG_SLOW_MS`.

## Backups

The DB runs in Postgres (Compose `db` service) and persists to the `postgres_data` named volume.

### Minimal backup (logical)

Example with `pg_dump` (run on the host):

```bash
# load variables from .env (trusted file only)
set -a
. ./.env
set +a

: "${POSTGRES_DB:?set POSTGRES_DB in .env}"
: "${POSTGRES_USER:?set POSTGRES_USER in .env}"
: "${POSTGRES_PORT:?set POSTGRES_PORT in .env}"
: "${POSTGRES_PASSWORD:?set POSTGRES_PASSWORD in .env (strong, unique value; not \"postgres\")}"

PGPASSWORD="$POSTGRES_PASSWORD" pg_dump \
  -h 127.0.0.1 -p "$POSTGRES_PORT" -U "$POSTGRES_USER" \
  -d "$POSTGRES_DB" \
  --format=custom > mission_control.backup
```

> **Note**
> For real production, prefer automated backups + retention + periodic restore drills.

## Upgrades / rollbacks

### Upgrade (Compose)

```bash
docker compose -f compose.yml --env-file .env up -d --build
```

### Rollback

Rollback typically means deploying a previous image/commit.

> **Warning**
> If you applied non-backward-compatible DB migrations, rolling back the app may require restoring the database.

## Common issues

### Frontend loads but API calls fail

- Confirm `NEXT_PUBLIC_API_URL` is set and reachable from the browser.
- Confirm backend CORS includes the frontend origin (`CORS_ORIGINS`).

### Auth mismatch

- Backend: `AUTH_MODE` (`local` or `clerk`)
- Frontend: `NEXT_PUBLIC_AUTH_MODE` should match
