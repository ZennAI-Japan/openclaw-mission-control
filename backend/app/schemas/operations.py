"""Schemas for Mission Control operations runtime endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class OperationsTaskRead(BaseModel):
    id: str
    project: str
    title: str
    objective: str
    priority: str
    status: str
    attempt: int
    created_at: datetime
    updated_at: datetime


class OperationsWorkerRead(BaseModel):
    session_key: str
    agent_id: str
    current_task_id: str | None
    last_heartbeat_at: datetime
    status: str


class OperationsEventRead(BaseModel):
    timestamp: datetime
    type: str
    task_id: str | None
    session_key: str | None
    payload: dict[str, object]


class OperationsUptimeRead(BaseModel):
    started_at: datetime
    now: datetime
    uptime_seconds: int = Field(ge=0)
    uptime_ratio: float = Field(ge=0, le=1)


class OperationsStallsRead(BaseModel):
    threshold_seconds: int = Field(ge=1)
    stalled_count: int = Field(ge=0)
    tasks: list[OperationsTaskRead]


class GenerateTasksRequest(BaseModel):
    goal: str = Field(min_length=3)
    project: str | None = None
    max_tasks: int = Field(default=5, ge=1, le=20)


class GenerateTasksResponse(BaseModel):
    generated: int
    added: int
    duplicate_or_blocked: int
    task_ids: list[str]


class DispatchTickResponse(BaseModel):
    dispatched_task_ids: list[str]
    refill_added: int
    queue_size: int
