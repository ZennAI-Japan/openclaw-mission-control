# ruff: noqa: INP001
from __future__ import annotations

from app.core.config import settings
from app.services import fifo_store


def test_fifo_store_upsert_get_and_filter(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "fifo_sqlite_path", str(tmp_path / "fifo.db"))

    fifo_store.upsert_task(
        task_id="t-1",
        group_id="ops",
        payload={"job": "one"},
        status="queued",
        retry_count=0,
    )
    fifo_store.upsert_task(
        task_id="t-2",
        group_id="ops",
        payload={"job": "two"},
        status="dead_letter",
        retry_count=4,
    )

    task = fifo_store.get_task("t-1")
    assert task is not None
    assert task.group_id == "ops"
    assert task.payload == {"job": "one"}
    assert task.status == "queued"

    all_tasks = fifo_store.list_tasks(limit=10)
    assert {item.task_id for item in all_tasks} == {"t-1", "t-2"}

    dead = fifo_store.list_tasks(status="dead_letter", limit=10)
    assert [item.task_id for item in dead] == ["t-2"]
