"""Operations runtime observability and control endpoints."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import require_admin_auth
from app.core.config import settings
from app.schemas.operations import (
    DispatchTickResponse,
    GenerateTasksRequest,
    GenerateTasksResponse,
    OperationsDashboardSummaryRead,
    OperationsEventRead,
    OperationsStallsRead,
    OperationsTaskRead,
    OperationsUptimeRead,
    OperationsWorkerRead,
)
from app.services.operations_control import (
    DISCORD_NOTIFIER,
    DISPATCHER_LOOP,
    GOAL_GENERATOR,
    RUNTIME_STARTED_AT,
    RUNTIME_STORE,
    STALL_THRESHOLD,
)

router = APIRouter(prefix="/operations", tags=["operations"])
ADMIN_AUTH_DEP = Depends(require_admin_auth)


def _require_operations_access(_auth: object = ADMIN_AUTH_DEP) -> None:
    if not settings.operations_api_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Operations runtime API is disabled.",
        )


def _require_runtime_writes_enabled() -> None:
    if not settings.operations_runtime_write_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operations runtime write endpoints are disabled.",
        )


def _worker_status_counts() -> dict[str, int | float]:
    total = len(RUNTIME_STORE.workers)
    offline = sum(1 for worker in RUNTIME_STORE.workers.values() if worker.status == "offline")
    busy = sum(1 for worker in RUNTIME_STORE.workers.values() if worker.status == "busy")
    idle = sum(1 for worker in RUNTIME_STORE.workers.values() if worker.status == "idle")
    online = total - offline
    utilization_denominator = online if online > 0 else total
    utilization = (busy / utilization_denominator) * 100 if utilization_denominator > 0 else 0.0
    return {
        "total": total,
        "online": online,
        "busy": busy,
        "idle": idle,
        "offline": offline,
        "utilization_pct": utilization,
    }


def _stall_metrics(*, now: datetime) -> tuple[dict[str, int], int, float]:
    stalled = RUNTIME_STORE.detect_stalled_tasks(threshold=STALL_THRESHOLD, now=now)
    if not stalled:
        return {}, 0, 0.0

    by_project: dict[str, int] = {}
    durations: list[int] = []
    for task in stalled:
        by_project[task.project] = by_project.get(task.project, 0) + 1
        durations.append(max(0, int((now - task.updated_at).total_seconds())))
    longest = max(durations, default=0)
    average = sum(durations) / len(durations) if durations else 0.0
    return by_project, longest, average


@router.get("/workers", response_model=list[OperationsWorkerRead])
def list_workers(_guard: None = Depends(_require_operations_access)) -> list[OperationsWorkerRead]:
    return [
        OperationsWorkerRead.model_validate(worker) for worker in RUNTIME_STORE.workers.values()
    ]


@router.get("/tasks", response_model=list[OperationsTaskRead])
def list_tasks(_guard: None = Depends(_require_operations_access)) -> list[OperationsTaskRead]:
    return [OperationsTaskRead.model_validate(task) for task in RUNTIME_STORE.tasks.values()]


@router.get("/events", response_model=list[OperationsEventRead])
def list_events(
    limit: int = 100,
    _guard: None = Depends(_require_operations_access),
) -> list[OperationsEventRead]:
    safe_limit = max(1, min(500, limit))
    return [
        OperationsEventRead.model_validate(event) for event in RUNTIME_STORE.events[-safe_limit:]
    ]


@router.get("/uptime", response_model=OperationsUptimeRead)
def get_uptime(_guard: None = Depends(_require_operations_access)) -> OperationsUptimeRead:
    now = datetime.now(UTC)
    delta = now - RUNTIME_STARTED_AT
    worker_counts = _worker_status_counts()
    return OperationsUptimeRead(
        started_at=RUNTIME_STARTED_AT,
        now=now,
        uptime_seconds=max(0, int(delta.total_seconds())),
        uptime_ratio=RUNTIME_STORE.uptime(),
        workers_total=worker_counts["total"],
        workers_online=worker_counts["online"],
        workers_busy=worker_counts["busy"],
        workers_idle=worker_counts["idle"],
        workers_offline=worker_counts["offline"],
        worker_utilization_pct=worker_counts["utilization_pct"],
        queue_depth=RUNTIME_STORE.queue_size(),
        queue_depth_by_priority=RUNTIME_STORE.queue_size_by_priority(),
    )


@router.get("/stalls", response_model=OperationsStallsRead)
def get_stalls(_guard: None = Depends(_require_operations_access)) -> OperationsStallsRead:
    now = datetime.now(UTC)
    stalled = RUNTIME_STORE.detect_stalled_tasks(threshold=STALL_THRESHOLD, now=now)
    by_project, longest_stall_seconds, average_stall_seconds = _stall_metrics(now=now)
    return OperationsStallsRead(
        threshold_seconds=int(STALL_THRESHOLD.total_seconds()),
        stalled_count=len(stalled),
        stalled_task_ids=[task.id for task in stalled],
        stalled_by_project=by_project,
        longest_stall_seconds=longest_stall_seconds,
        average_stall_seconds=average_stall_seconds,
        tasks=[OperationsTaskRead.model_validate(task) for task in stalled],
    )


@router.get("/dashboard/summary", response_model=OperationsDashboardSummaryRead)
def get_dashboard_summary(
    _guard: None = Depends(_require_operations_access),
) -> OperationsDashboardSummaryRead:
    now = datetime.now(UTC)
    worker_counts = _worker_status_counts()
    stalled = RUNTIME_STORE.detect_stalled_tasks(threshold=STALL_THRESHOLD, now=now)
    by_project, longest_stall_seconds, _average_stall_seconds = _stall_metrics(now=now)
    return OperationsDashboardSummaryRead(
        generated_at=now,
        uptime_seconds=max(0, int((now - RUNTIME_STARTED_AT).total_seconds())),
        queue_depth=RUNTIME_STORE.queue_size(),
        queue_depth_by_priority=RUNTIME_STORE.queue_size_by_priority(),
        workers_busy=int(worker_counts["busy"]),
        workers_online=int(worker_counts["online"]),
        worker_utilization_pct=float(worker_counts["utilization_pct"]),
        stalled_count=len(stalled),
        stalled_by_project=by_project,
        longest_stall_seconds=longest_stall_seconds,
    )


@router.post("/goals/generate", response_model=GenerateTasksResponse)
def generate_tasks(
    request: GenerateTasksRequest,
    _guard: None = Depends(_require_operations_access),
    _write_guard: None = Depends(_require_runtime_writes_enabled),
) -> GenerateTasksResponse:
    generator = GOAL_GENERATOR
    if request.project:
        generator = GOAL_GENERATOR.__class__(project=request.project)

    tasks = generator.generate(goal=request.goal, max_tasks=request.max_tasks)
    added_ids: list[str] = []
    for task in tasks:
        if RUNTIME_STORE.add_task(task):
            added_ids.append(task.id)

    return GenerateTasksResponse(
        generated=len(tasks),
        added=len(added_ids),
        duplicate_or_blocked=len(tasks) - len(added_ids),
        task_ids=added_ids,
    )


@router.post("/dispatch/tick", response_model=DispatchTickResponse)
def dispatch_tick(
    _guard: None = Depends(_require_operations_access),
    _write_guard: None = Depends(_require_runtime_writes_enabled),
) -> DispatchTickResponse:
    result = DISPATCHER_LOOP.run_tick(RUNTIME_STORE)
    DISCORD_NOTIFIER.notify_summary(
        {
            "dispatched": len(result.dispatched_task_ids),
            "refill_added": result.refill_added,
            "queue_size": RUNTIME_STORE.queue_size(),
        }
    )
    return DispatchTickResponse(
        dispatched_task_ids=result.dispatched_task_ids,
        refill_added=result.refill_added,
        queue_size=RUNTIME_STORE.queue_size(),
    )
