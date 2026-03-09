"""In-memory runtime primitives for Mission Control operations loops."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Callable, Literal

TaskPriority = Literal["P0", "P1", "P2"]
TaskStatus = Literal["queued", "running", "blocked", "done", "failed"]
WorkerStatus = Literal["idle", "busy", "offline"]
EventType = Literal["dispatch", "retry", "fail", "recover", "complete", "refill"]

_PRIORITY_ORDER: tuple[TaskPriority, ...] = ("P0", "P1", "P2")


@dataclass(slots=True)
class Task:
    id: str
    project: str
    title: str
    objective: str
    priority: TaskPriority
    status: TaskStatus = "queued"
    attempt: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class Worker:
    session_key: str
    agent_id: str
    current_task_id: str | None = None
    last_heartbeat_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    status: WorkerStatus = "idle"


@dataclass(slots=True)
class Event:
    timestamp: datetime
    type: EventType
    task_id: str | None
    session_key: str | None
    payload: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class InMemoryOperationsStore:
    """Simple in-memory operational store used by loop workers and tests."""

    tasks: dict[str, Task] = field(default_factory=dict)
    workers: dict[str, Worker] = field(default_factory=dict)
    events: list[Event] = field(default_factory=list)
    _queue: dict[TaskPriority, deque[str]] = field(
        default_factory=lambda: {priority: deque() for priority in _PRIORITY_ORDER}
    )

    def add_task(self, task: Task) -> None:
        self.tasks[task.id] = task
        if task.status == "queued":
            self._queue[task.priority].append(task.id)

    def upsert_worker(self, worker: Worker) -> None:
        self.workers[worker.session_key] = worker

    def queue_size(self) -> int:
        return sum(len(items) for items in self._queue.values())

    def queue_size_by_priority(self) -> dict[TaskPriority, int]:
        return {priority: len(self._queue[priority]) for priority in _PRIORITY_ORDER}

    def pop_next_task(self) -> Task | None:
        for priority in _PRIORITY_ORDER:
            queued = self._queue[priority]
            while queued:
                task_id = queued.popleft()
                task = self.tasks.get(task_id)
                if task is None or task.status != "queued":
                    continue
                return task
        return None

    def record_event(self, event: Event) -> None:
        self.events.append(event)

    def assign_task_to_worker(self, task: Task, worker: Worker, *, now: datetime | None = None) -> None:
        current_time = now or datetime.now(UTC)
        task.status = "running"
        task.updated_at = current_time
        worker.current_task_id = task.id
        worker.status = "busy"
        worker.last_heartbeat_at = current_time

    def maybe_refill_queue(
        self,
        *,
        low_watermark: int,
        refill_batch_size: int,
        refill_factory: Callable[[int], list[Task]] | None,
        now: datetime | None = None,
    ) -> int:
        if self.queue_size() >= low_watermark:
            return 0

        if refill_factory is None:
            return 0

        generated = refill_factory(refill_batch_size)
        for task in generated:
            self.add_task(task)

        self.record_event(
            Event(
                timestamp=now or datetime.now(UTC),
                type="refill",
                task_id=None,
                session_key=None,
                payload={"requested": refill_batch_size, "added": len(generated)},
            )
        )
        return len(generated)

    def detect_stalled_tasks(self, *, threshold: timedelta, now: datetime | None = None) -> list[Task]:
        current_time = now or datetime.now(UTC)
        stalled: list[Task] = []
        for task in self.tasks.values():
            if task.status != "running":
                continue
            if current_time - task.updated_at >= threshold:
                stalled.append(task)
        stalled.sort(key=lambda item: item.updated_at)
        return stalled
