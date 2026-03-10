"""Operations runtime observability and control endpoints."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter

from app.schemas.operations import (
    DispatchTickResponse,
    GenerateTasksRequest,
    GenerateTasksResponse,
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


@router.get("/workers", response_model=list[OperationsWorkerRead])
def list_workers() -> list[OperationsWorkerRead]:
    return [OperationsWorkerRead.model_validate(worker) for worker in RUNTIME_STORE.workers.values()]


@router.get("/tasks", response_model=list[OperationsTaskRead])
def list_tasks() -> list[OperationsTaskRead]:
    return [OperationsTaskRead.model_validate(task) for task in RUNTIME_STORE.tasks.values()]


@router.get("/events", response_model=list[OperationsEventRead])
def list_events(limit: int = 100) -> list[OperationsEventRead]:
    safe_limit = max(1, min(500, limit))
    return [
        OperationsEventRead.model_validate(event)
        for event in RUNTIME_STORE.events[-safe_limit:]
    ]


@router.get("/uptime", response_model=OperationsUptimeRead)
def get_uptime() -> OperationsUptimeRead:
    now = datetime.now(UTC)
    delta = now - RUNTIME_STARTED_AT
    return OperationsUptimeRead(
        started_at=RUNTIME_STARTED_AT,
        now=now,
        uptime_seconds=max(0, int(delta.total_seconds())),
        uptime_ratio=RUNTIME_STORE.uptime(),
    )


@router.get("/stalls", response_model=OperationsStallsRead)
def get_stalls() -> OperationsStallsRead:
    stalled = RUNTIME_STORE.detect_stalled_tasks(threshold=STALL_THRESHOLD)
    return OperationsStallsRead(
        threshold_seconds=int(STALL_THRESHOLD.total_seconds()),
        stalled_count=len(stalled),
        tasks=[OperationsTaskRead.model_validate(task) for task in stalled],
    )


@router.post("/goals/generate", response_model=GenerateTasksResponse)
def generate_tasks(request: GenerateTasksRequest) -> GenerateTasksResponse:
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
def dispatch_tick() -> DispatchTickResponse:
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
