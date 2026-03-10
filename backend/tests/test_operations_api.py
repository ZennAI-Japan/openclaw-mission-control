# ruff: noqa: INP001
"""API tests for Mission Control operations runtime endpoints."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import APIRouter, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api import operations as operations_api
from app.api.operations import router as operations_router
from app.core import auth as auth_module
from app.core.auth_mode import AuthMode
from app.core.config import settings
from app.db.session import get_session
from app.services.operations_dispatcher import DispatchResult
from app.services.operations_runtime import InMemoryOperationsStore, Task, Worker


async def _make_engine() -> AsyncEngine:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.connect() as conn, conn.begin():
        await conn.run_sync(SQLModel.metadata.create_all)
    return engine


def _build_test_app(
    session_maker: async_sessionmaker[AsyncSession],
) -> FastAPI:
    app = FastAPI()
    api_v1 = APIRouter(prefix="/api/v1")
    api_v1.include_router(operations_router)
    app.include_router(api_v1)

    async def _override_get_session() -> AsyncSession:
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_session] = _override_get_session
    app.dependency_overrides[auth_module.get_session] = _override_get_session
    return app


def _auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer operations-test-token"}


def _task(
    *,
    task_id: str,
    priority: str,
    project: str = "mission-control",
    status: str = "queued",
    updated_at: datetime | None = None,
) -> Task:
    created = datetime(2026, 3, 9, 12, 0, tzinfo=UTC)
    return Task(
        id=task_id,
        project=project,
        title=f"Task {task_id}",
        objective="objective",
        priority=priority,  # type: ignore[arg-type]
        status=status,  # type: ignore[arg-type]
        created_at=created,
        updated_at=updated_at or created,
    )


class _FixedDateTime(datetime):
    current = datetime(2026, 3, 10, 12, 0, tzinfo=UTC)

    @classmethod
    def now(cls, tz: object | None = None) -> datetime:
        if tz is None:
            return cls.current.replace(tzinfo=None)
        return cls.current.astimezone(tz)


@pytest.mark.asyncio
async def test_operations_api_requires_auth_and_write_guardrails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "auth_mode", AuthMode.LOCAL)
    monkeypatch.setattr(settings, "local_auth_token", "operations-test-token")
    monkeypatch.setattr(settings, "operations_api_enabled", True)
    monkeypatch.setattr(settings, "operations_runtime_write_enabled", False)

    store = InMemoryOperationsStore()
    store.add_task(_task(task_id="queued-p0", priority="P0"))
    store.upsert_worker(Worker(session_key="worker-1", agent_id="agent-1", status="idle"))
    monkeypatch.setattr(operations_api, "RUNTIME_STORE", store)
    monkeypatch.setattr(
        operations_api,
        "RUNTIME_STARTED_AT",
        datetime(2026, 3, 10, 11, 0, tzinfo=UTC),
    )
    monkeypatch.setattr(operations_api, "datetime", _FixedDateTime)

    engine = await _make_engine()
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    app = _build_test_app(session_maker)

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            missing = await client.get("/api/v1/operations/uptime")
            assert missing.status_code == 401

            uptime = await client.get("/api/v1/operations/uptime", headers=_auth_headers())
            assert uptime.status_code == 200
            assert uptime.json()["queue_depth"] == 1

            dispatch = await client.post(
                "/api/v1/operations/dispatch/tick", headers=_auth_headers()
            )
            assert dispatch.status_code == 403
            assert dispatch.json()["detail"] == "Operations runtime write endpoints are disabled."

            generate = await client.post(
                "/api/v1/operations/goals/generate",
                headers=_auth_headers(),
                json={"goal": "Stabilize runtime queue"},
            )
            assert generate.status_code == 403
            assert generate.json()["detail"] == "Operations runtime write endpoints are disabled."
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_operations_uptime_and_stalls_include_aggregates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed_now = datetime(2026, 3, 10, 12, 0, tzinfo=UTC)
    _FixedDateTime.current = fixed_now

    monkeypatch.setattr(settings, "auth_mode", AuthMode.LOCAL)
    monkeypatch.setattr(settings, "local_auth_token", "operations-test-token")
    monkeypatch.setattr(settings, "operations_api_enabled", True)
    monkeypatch.setattr(settings, "operations_runtime_write_enabled", True)

    store = InMemoryOperationsStore()
    store.add_task(_task(task_id="queued-p0", priority="P0", project="alpha"))
    store.add_task(
        _task(
            task_id="stalled-runner",
            priority="P1",
            project="alpha",
            status="running",
            updated_at=fixed_now - timedelta(minutes=31),
        )
    )
    store.add_task(
        _task(
            task_id="fresh-runner",
            priority="P2",
            project="beta",
            status="running",
            updated_at=fixed_now - timedelta(minutes=5),
        )
    )
    store.upsert_worker(Worker(session_key="busy-worker", agent_id="agent-1", status="busy"))
    store.upsert_worker(Worker(session_key="idle-worker", agent_id="agent-2", status="idle"))
    store.upsert_worker(Worker(session_key="offline-worker", agent_id="agent-3", status="offline"))

    notifications: list[dict[str, object]] = []

    class _Notifier:
        def notify_summary(self, payload: dict[str, object]) -> bool:
            notifications.append(payload)
            return True

    class _Dispatcher:
        def run_tick(self, runtime_store: InMemoryOperationsStore) -> DispatchResult:
            task = runtime_store.pop_next_task()
            assert task is not None
            return DispatchResult(dispatched_task_ids=[task.id], refill_added=0)

    monkeypatch.setattr(operations_api, "RUNTIME_STORE", store)
    monkeypatch.setattr(operations_api, "RUNTIME_STARTED_AT", fixed_now - timedelta(hours=2))
    monkeypatch.setattr(operations_api, "datetime", _FixedDateTime)
    monkeypatch.setattr(operations_api, "DISCORD_NOTIFIER", _Notifier())
    monkeypatch.setattr(operations_api, "DISPATCHER_LOOP", _Dispatcher())

    engine = await _make_engine()
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    app = _build_test_app(session_maker)

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            uptime = await client.get("/api/v1/operations/uptime", headers=_auth_headers())
            assert uptime.status_code == 200
            uptime_body = uptime.json()
            assert uptime_body["uptime_seconds"] == 7200
            assert uptime_body["workers_total"] == 3
            assert uptime_body["workers_online"] == 2
            assert uptime_body["workers_busy"] == 1
            assert uptime_body["workers_idle"] == 1
            assert uptime_body["workers_offline"] == 1
            assert uptime_body["worker_utilization_pct"] == 50.0
            assert uptime_body["queue_depth"] == 1
            assert uptime_body["queue_depth_by_priority"] == {"P0": 1, "P1": 0, "P2": 0}

            stalls = await client.get("/api/v1/operations/stalls", headers=_auth_headers())
            assert stalls.status_code == 200
            stalls_body = stalls.json()
            assert stalls_body["stalled_count"] == 1
            assert stalls_body["stalled_task_ids"] == ["stalled-runner"]
            assert stalls_body["stalled_by_project"] == {"alpha": 1}
            assert stalls_body["longest_stall_seconds"] == 1860
            assert stalls_body["average_stall_seconds"] == 1860.0

            dashboard = await client.get(
                "/api/v1/operations/dashboard/summary", headers=_auth_headers()
            )
            assert dashboard.status_code == 200
            dashboard_body = dashboard.json()
            assert dashboard_body["queue_depth"] == 1
            assert dashboard_body["workers_busy"] == 1
            assert dashboard_body["workers_online"] == 2
            assert dashboard_body["worker_utilization_pct"] == 50.0
            assert dashboard_body["stalled_count"] == 1
            assert dashboard_body["stalled_by_project"] == {"alpha": 1}

            dispatch = await client.post(
                "/api/v1/operations/dispatch/tick", headers=_auth_headers()
            )
            assert dispatch.status_code == 200
            assert dispatch.json() == {
                "dispatched_task_ids": ["queued-p0"],
                "refill_added": 0,
                "queue_size": 0,
            }
            assert notifications == [{"dispatched": 1, "refill_added": 0, "queue_size": 0}]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_operations_api_can_be_disabled_entirely(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "auth_mode", AuthMode.LOCAL)
    monkeypatch.setattr(settings, "local_auth_token", "operations-test-token")
    monkeypatch.setattr(settings, "operations_api_enabled", False)

    engine = await _make_engine()
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    app = _build_test_app(session_maker)

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.get("/api/v1/operations/uptime", headers=_auth_headers())
            assert response.status_code == 503
            assert response.json()["detail"] == "Operations runtime API is disabled."
    finally:
        await engine.dispose()
