"""FIFO queue API endpoints for operations workflows."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import require_admin_auth
from app.schemas.fifo_queue import (
    FifoEnqueueRequest,
    FifoEnqueueResponse,
    FifoListResponse,
    FifoRetryResponse,
    FifoTaskRead,
)
from app.services.fifo_queue import enqueue_task, get_task_status, list_task_statuses, retry_task

router = APIRouter(prefix="/operations/fifo", tags=["operations"])
ADMIN_AUTH_DEP = Depends(require_admin_auth)


@router.post("/enqueue", response_model=FifoEnqueueResponse, status_code=status.HTTP_202_ACCEPTED)
def enqueue_fifo_task(
    body: FifoEnqueueRequest,
    _auth: object = ADMIN_AUTH_DEP,
) -> FifoEnqueueResponse:
    task_id = enqueue_task(group_id=body.group_id, payload=body.payload)
    return FifoEnqueueResponse(task_id=task_id)


@router.get("/tasks", response_model=FifoListResponse)
def list_fifo_tasks(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _auth: object = ADMIN_AUTH_DEP,
) -> FifoListResponse:
    records = list_task_statuses(status=status_filter, limit=limit, offset=offset)
    return FifoListResponse(
        items=[FifoTaskRead.model_validate(record.__dict__) for record in records]
    )


@router.get("/tasks/dead-letter", response_model=FifoListResponse)
def list_dead_letter_tasks(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _auth: object = ADMIN_AUTH_DEP,
) -> FifoListResponse:
    records = list_task_statuses(status="dead_letter", limit=limit, offset=offset)
    return FifoListResponse(
        items=[FifoTaskRead.model_validate(record.__dict__) for record in records]
    )


@router.get("/tasks/{task_id}", response_model=FifoTaskRead)
def get_fifo_task(task_id: str, _auth: object = ADMIN_AUTH_DEP) -> FifoTaskRead:
    task = get_task_status(task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return FifoTaskRead.model_validate(task.__dict__)


@router.post("/tasks/{task_id}/retry", response_model=FifoRetryResponse)
def retry_fifo_task(task_id: str, _auth: object = ADMIN_AUTH_DEP) -> FifoRetryResponse:
    try:
        task = retry_task(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found") from exc
    return FifoRetryResponse(task=FifoTaskRead.model_validate(task.__dict__))
