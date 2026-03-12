"""Schemas for FIFO queue APIs."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

TaskStatus = Literal["queued", "processing", "succeeded", "failed", "dead_letter"]


class FifoEnqueueRequest(BaseModel):
    group_id: str = Field(min_length=1, max_length=128)
    payload: dict[str, Any]


class FifoTaskRead(BaseModel):
    task_id: str
    group_id: str
    payload: dict[str, Any]
    status: TaskStatus
    retry_count: int
    created_at: str
    updated_at: str


class FifoRetryResponse(BaseModel):
    task: FifoTaskRead


class FifoEnqueueResponse(BaseModel):
    task_id: str


class FifoListResponse(BaseModel):
    items: list[FifoTaskRead]
