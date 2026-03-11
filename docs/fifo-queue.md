# FIFO Queue Integration (Mission Control)

Mission Control now includes a local FIFO job subsystem built with:

- Redis Streams (`XADD`, `XREADGROUP`, `XACK`, `XPENDING`, `XAUTOCLAIM`)
- SQLite task-state persistence (`fifo_tasks` table)
- FastAPI endpoints for enqueue/list/status/retry/dead-letter visibility
- Dedicated worker process (`scripts/rq-docker fifo-worker`)

## Architecture

1. API enqueue writes Redis stream entry via `XADD`.
2. API also upserts SQLite state as `queued`.
3. Worker consumes from consumer group using `XREADGROUP`.
4. Worker marks task `processing` in SQLite.
5. Success path: `succeeded` + `XACK`.
6. Failure path:
   - if retry <= max: mark `failed`, re-enqueue via `XADD`, `XACK` old entry
   - if retry exceeded: mark `dead_letter`, `XACK`
7. Recovery path: worker checks `XPENDING` and reclaims stale deliveries with `XAUTOCLAIM`.

## Task schema / statuses

Stream fields:

- `task_id`
- `group_id`
- `payload` (JSON string)
- `retry_count`
- `status`

SQLite table:

```sql
CREATE TABLE IF NOT EXISTS fifo_tasks (
  task_id TEXT PRIMARY KEY,
  group_id TEXT NOT NULL,
  payload TEXT NOT NULL,
  status TEXT NOT NULL,
  retry_count INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
```

Status values:

- `queued`
- `processing`
- `succeeded`
- `failed`
- `dead_letter`

## API endpoints

Under `/api/v1/operations/fifo`:

- `POST /enqueue` – enqueue a task
- `GET /tasks` – list tasks (`?status=...&limit=...&offset=...`)
- `GET /tasks/{task_id}` – task status/details
- `POST /tasks/{task_id}/retry` – force retry by re-enqueueing with incremented retry count
- `GET /tasks/dead-letter` – dead-letter visibility

## Run locally (Docker Compose)

```bash
docker compose up --build
```

This starts:

- `redis` (AOF enabled + persistent `redis_data` volume)
- `backend` (API + SQLite task state mounted at `/data/tasks.db`)
- `webhook-worker`
- `fifo-worker`
- other standard Mission Control services

## Relevant env vars

- `FIFO_REDIS_URL`
- `FIFO_STREAM_NAME`
- `FIFO_CONSUMER_GROUP`
- `FIFO_CONSUMER_NAME`
- `FIFO_SQLITE_PATH`
- `FIFO_MAX_RETRIES`
- `FIFO_CLAIM_MIN_IDLE_MS`
- `FIFO_READ_COUNT`
- `FIFO_BLOCK_MS`
- `FIFO_WORKER_SLEEP_SECONDS`
