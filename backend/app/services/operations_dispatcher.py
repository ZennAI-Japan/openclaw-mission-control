"""Dispatcher loop primitives for Mission Control operations runtime."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.services.operations_runtime import Event, InMemoryOperationsStore


@dataclass(slots=True)
class DispatchResult:
    dispatched_task_ids: list[str]
    refill_added: int


class DispatcherLoop:
    def __init__(
        self,
        *,
        max_concurrency: int,
        low_watermark: int,
        refill_batch_size: int,
    ) -> None:
        self._max_concurrency = max(0, max_concurrency)
        self._low_watermark = max(0, low_watermark)
        self._refill_batch_size = max(0, refill_batch_size)

    def run_tick(self, store: InMemoryOperationsStore, *, now: datetime | None = None) -> DispatchResult:
        current_time = now or datetime.now(UTC)
        refill_added = store.maybe_refill_queue(
            low_watermark=self._low_watermark,
            refill_batch_size=self._refill_batch_size,
            refill_factory=None,
            now=current_time,
        )

        idle_workers = [worker for worker in store.workers.values() if worker.status == "idle"]
        available_slots = min(len(idle_workers), self._max_concurrency)

        dispatched: list[str] = []
        for worker in idle_workers[:available_slots]:
            task = store.pop_next_task()
            if task is None:
                break
            store.assign_task_to_worker(task, worker, now=current_time)
            store.record_event(
                Event(
                    timestamp=current_time,
                    type="dispatch",
                    task_id=task.id,
                    session_key=worker.session_key,
                    payload={"priority": task.priority, "project": task.project},
                )
            )
            dispatched.append(task.id)

        return DispatchResult(dispatched_task_ids=dispatched, refill_added=refill_added)
