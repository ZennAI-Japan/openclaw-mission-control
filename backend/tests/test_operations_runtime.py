# ruff: noqa: INP001

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.services.operations_dispatcher import DispatcherLoop
from app.services.operations_runtime import InMemoryOperationsStore, Task, Worker


def _task(*, task_id: str, priority: str, status: str = "queued", updated_at: datetime | None = None) -> Task:
    created = datetime(2026, 3, 9, 0, 0, tzinfo=UTC)
    return Task(
        id=task_id,
        project="core",
        title=f"Task {task_id}",
        objective="objective",
        priority=priority,  # type: ignore[arg-type]
        status=status,  # type: ignore[arg-type]
        created_at=created,
        updated_at=updated_at or created,
    )


def test_queue_priority_pop_order() -> None:
    store = InMemoryOperationsStore()
    store.add_task(_task(task_id="p2", priority="P2"))
    store.add_task(_task(task_id="p0", priority="P0"))
    store.add_task(_task(task_id="p1", priority="P1"))

    first = store.pop_next_task()
    second = store.pop_next_task()
    third = store.pop_next_task()

    assert [first.id, second.id, third.id] == ["p0", "p1", "p2"]


def test_dispatcher_assigns_up_to_available_slots() -> None:
    store = InMemoryOperationsStore()
    store.add_task(_task(task_id="t1", priority="P0"))
    store.add_task(_task(task_id="t2", priority="P1"))
    store.add_task(_task(task_id="t3", priority="P2"))

    store.upsert_worker(Worker(session_key="w1", agent_id="a1"))
    store.upsert_worker(Worker(session_key="w2", agent_id="a2"))
    store.upsert_worker(Worker(session_key="w3", agent_id="a3", status="offline"))

    loop = DispatcherLoop(max_concurrency=2, low_watermark=10, refill_batch_size=20)
    result = loop.run_tick(store)

    assert result.dispatched_task_ids == ["t1", "t2"]
    assert store.tasks["t1"].status == "running"
    assert store.tasks["t2"].status == "running"
    assert store.tasks["t3"].status == "queued"
    assert len(store.events) == 2
    assert {event.type for event in store.events} == {"dispatch"}


def test_stall_detection_returns_only_running_over_threshold() -> None:
    now = datetime(2026, 3, 9, 10, 0, tzinfo=UTC)
    store = InMemoryOperationsStore()
    store.add_task(
        _task(
            task_id="running-stalled",
            priority="P0",
            status="running",
            updated_at=now - timedelta(minutes=30),
        )
    )
    store.add_task(
        _task(
            task_id="running-fresh",
            priority="P1",
            status="running",
            updated_at=now - timedelta(minutes=5),
        )
    )
    store.add_task(
        _task(
            task_id="queued-old",
            priority="P2",
            status="queued",
            updated_at=now - timedelta(hours=1),
        )
    )

    stalled = store.detect_stalled_tasks(threshold=timedelta(minutes=15), now=now)

    assert [task.id for task in stalled] == ["running-stalled"]


def test_refill_skeleton_noop_without_factory() -> None:
    store = InMemoryOperationsStore()
    added = store.maybe_refill_queue(low_watermark=10, refill_batch_size=20, refill_factory=None)

    assert added == 0
    assert store.events == []
