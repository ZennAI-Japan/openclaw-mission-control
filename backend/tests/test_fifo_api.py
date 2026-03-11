# ruff: noqa: INP001
from __future__ import annotations

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from app.api.deps import require_admin_auth
from app.api.fifo_queue import router as fifo_router
from app.core import auth as auth_module
from app.db.session import get_session
from app.services.fifo_store import FifoTaskRecord


def _build_app() -> FastAPI:
    app = FastAPI()
    api_v1 = APIRouter(prefix="/api/v1")
    api_v1.include_router(fifo_router)
    app.include_router(api_v1)

    async def _override_get_session():
        yield None

    app.dependency_overrides[get_session] = _override_get_session
    app.dependency_overrides[auth_module.get_session] = _override_get_session
    app.dependency_overrides[require_admin_auth] = lambda: {"sub": "test-admin"}
    return app


def _headers() -> dict[str, str]:
    return {"Authorization": "Bearer token"}


def _record(task_id: str, status: str = "queued", retry_count: int = 0) -> FifoTaskRecord:
    return FifoTaskRecord(
        task_id=task_id,
        group_id="ops",
        payload={"job": task_id},
        status=status,
        retry_count=retry_count,
        created_at="2026-03-11T00:00:00+00:00",
        updated_at="2026-03-11T00:00:00+00:00",
    )


def test_fifo_api_core_paths(monkeypatch):
    from app.api import fifo_queue as fifo_api

    monkeypatch.setattr(fifo_api, "enqueue_task", lambda **_: "task-1")
    monkeypatch.setattr(fifo_api, "list_task_statuses", lambda **_: [_record("task-1")])
    monkeypatch.setattr(fifo_api, "get_task_status", lambda task_id: _record(task_id))
    monkeypatch.setattr(fifo_api, "retry_task", lambda task_id: _record(task_id, retry_count=1))

    app = _build_app()
    client = TestClient(app)

    enqueue = client.post(
        "/api/v1/operations/fifo/enqueue",
        json={"group_id": "ops", "payload": {"hello": "world"}},
        headers=_headers(),
    )
    assert enqueue.status_code == 202
    assert enqueue.json()["task_id"] == "task-1"

    listed = client.get("/api/v1/operations/fifo/tasks", headers=_headers())
    assert listed.status_code == 200
    assert listed.json()["items"][0]["task_id"] == "task-1"

    status = client.get("/api/v1/operations/fifo/tasks/task-1", headers=_headers())
    assert status.status_code == 200
    assert status.json()["task_id"] == "task-1"

    retried = client.post("/api/v1/operations/fifo/tasks/task-1/retry", headers=_headers())
    assert retried.status_code == 200
    assert retried.json()["task"]["retry_count"] == 1
