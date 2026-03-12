"""FIFO worker implementation over Redis Streams consumer groups."""

from __future__ import annotations

import time
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger
from app.services.fifo_queue import (
    StreamTask,
    ack,
    claim_stale_messages,
    enqueue_task,
    read_new_messages,
)
from app.services.fifo_store import upsert_task

logger = get_logger(__name__)


def _process_payload(payload: dict[str, Any]) -> None:
    if bool(payload.get("force_fail")):
        raise RuntimeError("forced failure for retry handling")


def _handle_task(task: StreamTask) -> None:
    upsert_task(
        task_id=task.task_id,
        group_id=task.group_id,
        payload=task.payload,
        status="processing",
        retry_count=task.retry_count,
    )
    try:
        _process_payload(task.payload)
        upsert_task(
            task_id=task.task_id,
            group_id=task.group_id,
            payload=task.payload,
            status="succeeded",
            retry_count=task.retry_count,
        )
        ack(task.entry_id)
    except Exception as exc:  # noqa: BLE001
        next_retry = task.retry_count + 1
        if next_retry > settings.fifo_max_retries:
            upsert_task(
                task_id=task.task_id,
                group_id=task.group_id,
                payload=task.payload,
                status="dead_letter",
                retry_count=next_retry,
            )
            ack(task.entry_id)
            logger.error("fifo.worker.dead_letter task_id=%s error=%s", task.task_id, exc)
            return
        upsert_task(
            task_id=task.task_id,
            group_id=task.group_id,
            payload=task.payload,
            status="failed",
            retry_count=next_retry,
        )
        enqueue_task(
            group_id=task.group_id,
            payload=task.payload,
            task_id=task.task_id,
            retry_count=next_retry,
        )
        ack(task.entry_id)


def run_once() -> int:
    processed = 0
    for task in claim_stale_messages():
        _handle_task(task)
        processed += 1
    for task in read_new_messages(count=settings.fifo_read_count, block_ms=settings.fifo_block_ms):
        _handle_task(task)
        processed += 1
    return processed


def run_worker() -> None:
    logger.info(
        "fifo.worker.started stream=%s group=%s",
        settings.fifo_stream_name,
        settings.fifo_consumer_group,
    )
    while True:
        run_once()
        time.sleep(settings.fifo_worker_sleep_seconds)
