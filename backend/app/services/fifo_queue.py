"""Redis Stream FIFO queue integration with SQLite task state."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any

from redis import Redis
from redis.exceptions import ResponseError

from app.core.config import settings
from app.services.fifo_store import FifoTaskRecord, get_task, list_tasks, upsert_task


@dataclass(frozen=True)
class StreamTask:
    entry_id: str
    task_id: str
    group_id: str
    payload: dict[str, Any]
    retry_count: int
    status: str


def redis_client() -> Redis:
    return Redis.from_url(settings.fifo_redis_url, decode_responses=True)


def ensure_group(r: Redis | None = None) -> None:
    client = r or redis_client()
    try:
        client.xgroup_create(
            name=settings.fifo_stream_name,
            groupname=settings.fifo_consumer_group,
            id="0",
            mkstream=True,
        )
    except ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise


def enqueue_task(*, group_id: str, payload: dict[str, Any], task_id: str | None = None, retry_count: int = 0) -> str:
    client = redis_client()
    ensure_group(client)
    resolved_task_id = task_id or str(uuid.uuid4())
    fields = {
        "task_id": resolved_task_id,
        "group_id": group_id,
        "payload": json.dumps(payload, ensure_ascii=False),
        "retry_count": str(retry_count),
        "status": "queued",
    }
    client.xadd(settings.fifo_stream_name, fields=fields)
    upsert_task(
        task_id=resolved_task_id,
        group_id=group_id,
        payload=payload,
        status="queued",
        retry_count=retry_count,
    )
    return resolved_task_id


def read_new_messages(*, count: int = 10, block_ms: int = 5000) -> list[StreamTask]:
    client = redis_client()
    ensure_group(client)
    records = client.xreadgroup(
        groupname=settings.fifo_consumer_group,
        consumername=settings.fifo_consumer_name,
        streams={settings.fifo_stream_name: ">"},
        count=max(1, count),
        block=max(0, block_ms),
    )
    return _to_stream_tasks(records)


def claim_stale_messages(*, min_idle_ms: int | None = None, count: int = 20) -> list[StreamTask]:
    client = redis_client()
    ensure_group(client)
    summary = client.xpending(settings.fifo_stream_name, settings.fifo_consumer_group)
    if isinstance(summary, dict) and int(summary.get("pending", 0)) == 0:
        return []

    _cursor, claimed, _deleted = client.xautoclaim(
        settings.fifo_stream_name,
        settings.fifo_consumer_group,
        settings.fifo_consumer_name,
        min_idle_time=min_idle_ms or settings.fifo_claim_min_idle_ms,
        start_id="0-0",
        count=max(1, count),
    )
    return [
        _entry_to_stream_task(entry_id=str(entry_id), fields=fields)
        for entry_id, fields in claimed
    ]


def ack(entry_id: str) -> None:
    client = redis_client()
    client.xack(settings.fifo_stream_name, settings.fifo_consumer_group, entry_id)


def get_task_status(task_id: str) -> FifoTaskRecord | None:
    return get_task(task_id)


def list_task_statuses(*, status: str | None = None, limit: int = 100, offset: int = 0) -> list[FifoTaskRecord]:
    return list_tasks(status=status, limit=limit, offset=offset)


def retry_task(task_id: str) -> FifoTaskRecord:
    task = get_task(task_id)
    if task is None:
        raise KeyError(task_id)
    next_retry = task.retry_count + 1
    enqueue_task(group_id=task.group_id, payload=task.payload, task_id=task.task_id, retry_count=next_retry)
    updated = get_task(task_id)
    if updated is None:
        raise RuntimeError("Failed to reload retried task")
    return updated


def _to_stream_tasks(records: object) -> list[StreamTask]:
    tasks: list[StreamTask] = []
    for _stream_name, entries in records or []:
        for entry_id, fields in entries:
            tasks.append(_entry_to_stream_task(entry_id=str(entry_id), fields=fields))
    return tasks


def _entry_to_stream_task(*, entry_id: str, fields: dict[str, str]) -> StreamTask:
    payload = json.loads(fields["payload"])
    return StreamTask(
        entry_id=entry_id,
        task_id=fields["task_id"],
        group_id=fields["group_id"],
        payload=payload,
        retry_count=int(fields.get("retry_count", "0")),
        status=fields.get("status", "queued"),
    )
